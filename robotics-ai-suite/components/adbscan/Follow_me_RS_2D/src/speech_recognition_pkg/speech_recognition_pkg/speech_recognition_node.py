#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import rclpy
from rclpy.node import Node
import wave
from ament_index_python.packages import get_package_share_directory
import os
import numpy as np
from numpy.linalg import norm
import librosa
import scipy
from openvino.inference_engine import IECore
import simpleaudio as sa
import sounddevice as sd

from std_msgs.msg import String
from follow_me_interfaces.msg import AudioCommand



class QuartzNet:
    pad_to = 16
    alphabet = " abcdefghijklmnopqrstuvwxyz'"

    def __init__(self, ie, model_path, input_shape, device):
        assert not input_shape[2] % self.pad_to, f"{self.pad_to} must be a divisor of input_shape's third dimension"
        self.ie = ie
        network = self.ie.read_network(model_path)
        if len(network.input_info) != 1:
            raise RuntimeError('QuartzNet must have one input')

        model_input_shape = next(iter(network.input_info.values())).input_data.shape
        if len(model_input_shape) != 3:
            raise RuntimeError('QuartzNet input must be 3-dimensional')
        if model_input_shape[1] != input_shape[1]:
            raise RuntimeError("QuartzNet input second dimension can't be reshaped")
        if model_input_shape[2] % self.pad_to:
            raise RuntimeError(f'{self.pad_to} must be a divisor of QuartzNet input third dimension')
        if len(network.outputs) != 1:
            raise RuntimeError('QuartzNet must have one output')
        model_output_shape = next(iter(network.outputs.values())).shape
        if len(model_output_shape) != 3:
            raise RuntimeError('QuartzNet output must be 3-dimensional')
        if model_output_shape[2] != len(self.alphabet) + 1:  # +1 for blank char
            raise RuntimeError(f'QuartzNet output third dimension size must be {len(self.alphabet) + 1}')
        network.reshape({next(iter(network.input_info)): input_shape})
        self.exec_net = self.ie.load_network(network, device)

    def infer(self, melspectrogram):
        return next(iter(self.exec_net.infer({next(iter(self.exec_net.input_info)): melspectrogram}).values()))

    @classmethod
    def audio_to_melspectrum(cls, audio, sampling_rate):
        assert sampling_rate == 16000, "Only 16 KHz audio supported"
        preemph = 0.97
        # To increase signal to noise ratio we use a pre-emphasis filter.
        # Equation we use to apply pre-emphasis filter on signal x is  y(t) = x(t)− a * x(t−1) where a typically takes values 0.95 or 0.97.
        preemphased = np.concatenate([audio[:1], audio[1:] - preemph * audio[:-1].astype(np.float32)])
        print("preemphased done \n")
        # Short-time Fourier transform (STFT) is a sequence of Fourier transforms of a windowed signal.
        # n_fft - The number of rows in the STFT matrix is (1+ n_fft/2). (n_fft = Win_length).
        # Win_length - Each frame of audio is windowed by a window of length win_length.
        # Hop_length - number of samples between each successive FFT window.
        # Hann window has low side lobes compared to rectangular window, so hann window results in low leakage.
        win_length = round(sampling_rate * 0.02)
        spec = np.abs(librosa.stft(preemphased, n_fft=win_length, hop_length=round(sampling_rate * 0.01),
            win_length=win_length, center=True, window=scipy.signal.windows.hann(win_length), pad_mode='reflect'))
        # spec = np.abs(librosa.core.spectrum.stft(preemphased, n_fft=win_length, hop_length=round(sampling_rate * 0.01),
        #     win_length=win_length, center=True, window=scipy.signal.windows.hann(win_length), pad_mode='reflect'))
       
        print("spec done \n")
        # Mel scale is a unit of pitch such that equal distances in pitch sounded equally distant to the listener.
        # A Mel spectrogram is a spectrogram where the frequencies are converted to the Mel scale.
        # Below is code to create Mel basis or triangular filter banks.
        mel_basis = librosa.filters.mel(sr=sampling_rate, n_fft=win_length, n_mels=64, fmin=0.0, fmax=8000.0, norm='slaney', htk=False)
        print("mel_basis: Done \n")
        # To have Perceptually relevant frequency representation we calculate Mel Spectrogram.
        # Mel Spectrogram is a dot product of Mel filter banks and Spectrogram.
        # To have Perceptually relevant amplitude representation Log is applied to Mel Spectrogram.
        log_melspectrum = np.log(np.dot(mel_basis, np.power(spec, 2)) + 2 ** -24)
        # We normalize values of Log Mel Spectrogram for Neural networks to have a much easier time learning.
        # so we normalize the mel spectrogram at time of inference.
        normalized = (log_melspectrum - log_melspectrum.mean(1)[:, None]) / (log_melspectrum.std(1)[:, None] + 1e-5)
        # We add zeros to Log Mel Spectrogram to satisfy model input dimension constraints.
        remainder = normalized.shape[1] % cls.pad_to
        if remainder != 0:
            return np.pad(normalized, ((0, 0), (0, cls.pad_to - remainder)))[None]
        return normalized[None]

    @classmethod
    def ctc_greedy_decode(cls, pred):
        prev_id = blank_id = len(cls.alphabet)
        transcription = []
        # Every output has 29 probabilities where 26 for alphabets, 1 for space, 1 for  ‘ , 1 for blank. Maximum from these probabilities  is chosen for corresponding output.
        # Raw output is collapsed to produce required output which does not have repetitive characters and blanks.
        # AAAAAAAA          is   A
        # AAABBBBB          is   AB
        # AA__BBBB          is   AB
        # AA___AAA          is   AA
        for idx in pred[0].argmax(1):
            if prev_id != idx != blank_id:
                transcription.append(cls.alphabet[idx])
            prev_id = idx

        return ''.join(transcription)


class speech_recognizer(Node):
    def __init__(self):
        super().__init__("speech_recognition_node")
        self.get_logger().info("speech_recognition_node has been started")
        # declare parameters
        self.audio_transcript_ = "no_action"
        self.allowed_commands_ = ["start following", "stop following", "turn left", "turn right", "speed up", "slow down"]
        self.outgoing_commands_ = ["start", "stop", "left", "right", "speed", "slow"]
        self.declare_parameter("audio_input", "recorded")
        self.declare_parameter("audio_publish_frequency", 2.0)
        self.declare_parameter("sampling_rate", 16000)
        self.declare_parameter("live_audio_length_in_seconds", 20)
        self.declare_parameter("device_name", "CPU")
        self.device_name_ = self.get_parameter("device_name").value
        self.device_name_ = self.device_name_.upper()
        if self.device_name_ not in ["CPU", "GPU", "NPU"]:
            self.device_name_ = "CPU"
        self.get_logger().info("using device: {}".format(self.device_name_))
        self.fs = self.get_parameter("sampling_rate").value
        self.live_audio_length = self.get_parameter("live_audio_length_in_seconds").value
        self.audio_input_type_ = self.get_parameter("audio_input").value
        self.audio_publish_frequency_ = self.get_parameter("audio_publish_frequency").value
        if self.audio_input_type_ not in ["recorded", "live"]:
            self.get_logger().error("Wrong audio input type. Supported options: recorded, live")
        if self.audio_input_type_ == "live":
            self.audio_input_timer_ = self.create_timer(1.0/self.audio_publish_frequency_, self.record_audio)
        else:
            self.audio_subscriber_ = self.create_subscription(String, "audio_filename", self.audio_topic_callback, 10)
            # self.get_logger().info("Live audio input is not supported yet")
        # declare gesture publisher
        self.audio_command_publisher_ = self.create_publisher(AudioCommand, "audio_command", 10)
        self.audio_publish_timer_ = self.create_timer(1.0/self.audio_publish_frequency_, self.publish_audio_command)


    def audio_topic_callback(self, msg):
        audio_filename = msg.data
        self.process_audio_file(audio_filename)
        
    def record_audio(self):
        myrecording = sd.rec(int(self.live_audio_length * self.fs), samplerate=self.fs, channels=1, dtype=np.int16)
        sd.wait()
        if myrecording is not None:
            write("recorded.wav", self.fs, myrecording)
            process_audio_file("recorded.wav")
        else:
            process_audio_file("")

    def process_audio_file(self, audio_filename):
        if audio_filename != "":
            self.audio_file_ = os.path.join(get_package_share_directory('speech_recognition_pkg'), 'config','audio_files',audio_filename)
            if not os.path.isfile(self.audio_file_):
                self.get_logger().error("recorded audio file: {} is not found".format(self.audio_file_))
                return
            with wave.open(self.audio_file_, 'rb') as wave_read:
                # print("opened audio file")
                wave_obj = sa.WaveObject.from_wave_file(self.audio_file_)
                play_obj = wave_obj.play()   # Audio is played from device
                play_obj.wait_done()
                channel_num, sample_width, sampling_rate, pcm_length, compression_type, _ = wave_read.getparams()
                # print("get params from audio file")
                assert sample_width == 2, "Only 16-bit WAV PCM supported"
                assert compression_type == 'NONE', "Only linear PCM WAV files supported"
                assert channel_num == 1, "Only mono WAV PCM supported"
                assert sampling_rate == 16000, "Only 16 KHz audio supported"
                audio = np.frombuffer(wave_read.readframes(pcm_length * channel_num), dtype=np.int16).reshape((pcm_length, channel_num))
                # Wave_read.readframes(n) reads and returns at most n frames of audio, as a bytes object
                print("Reading audio file: DONE \n")
                # print(audio.shape)
            # Audio converted to Log Mel Spectrogram using Audio to Mel spectrogram Method.
            log_melspectrum = QuartzNet.audio_to_melspectrum(audio.flatten(), sampling_rate)
            # Loading QuartzNet model
            self.model_file_ = os.path.join(get_package_share_directory('speech_recognition_pkg'), 'config','model_files','quartznet-15x5-en.xml')
            quartz_net = QuartzNet(IECore(), self.model_file_, log_melspectrum.shape, device=self.device_name_)
            # Inference on Log Mel Spectrogram which outputs characters with probabilities.
            character_probs = quartz_net.infer(log_melspectrum)
            # Ctc greedy decoder is used to generate Text or Transcription.
            transcription = QuartzNet.ctc_greedy_decode(character_probs)

            print("\ntext from audio file  :  ",str(transcription))
            audio_command = str(transcription)

            similarity_score = [self.string_similarity(audio_command, command) for command in self.allowed_commands_]
            command_idx = np.argmax(similarity_score)
            max_similarity = np.max(similarity_score)
            if max_similarity <= 0.75:
                self.get_logger().info("Audio command not recognized")
                self.audio_transcript_ = "no_action"
            else:
                self.audio_transcript_ = self.outgoing_commands_[command_idx]
        else:
            self.audio_transcript_ = "no_action"


    def publish_audio_command(self):
        audio_msg = AudioCommand()
        audio_msg.audio_command = self.audio_transcript_
        self.audio_command_publisher_.publish(audio_msg)
        self.get_logger().info("Publishing audio command: {}".format(audio_msg.audio_command))

    def string_similarity (self, s1, s2):
        if len(s1) == 0 or len(s2) == 0:
            return 0.0
        s1_vec = [ord(ch) for ch in s1]
        s2_vec = [ord(ch) for ch in s2]
        if len(s1_vec) > len(s2_vec):
            s2_vec.extend([0]*(len(s1_vec) - len(s2_vec)))
        elif len(s2_vec) > len(s1_vec):
            s1_vec.extend([0]*(len(s2_vec) - len(s1_vec)))

        score = np.dot(s1_vec, s2_vec)/(norm(s1_vec)*norm(s2_vec))
        return score

def main(args=None):
    rclpy.init(args= args)
    node = speech_recognizer()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()