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
from openvino.inference_engine import IECore
import simpleaudio as sa

from models.forward_tacotron_ie import ForwardTacotronIE
from models.mel2wave_ie import WaveRNNIE, MelGANIE
from tqdm import tqdm

from std_msgs.msg import String
from std_msgs.msg import Bool
from geometry_msgs.msg import Point
from follow_me_interfaces.msg import AudioCommand
from follow_me_interfaces.msg import GestureCategory

from nav_msgs.msg import Odometry

class text_to_speech(Node):
    def __init__(self):
        super().__init__("text_to_speech_node")
        
        # declare parameters
        self.declare_parameter("tbot_odom_topic_name", "/tb3/odom")
        self.declare_parameter("gbot_odom_topic_name", "/guide_robot/odom")
        self.declare_parameter("audio_command_topic_name", "audio_command")
        self.declare_parameter("gesture_topic_name", "gesture")
        self.declare_parameter("motor_state_topic_name", "motor_state")
        self.declare_parameter("target_loc_topic_name", "target_loc")
        self.declare_parameter("audio_play_frequency", 2)
        self.declare_parameter("distance_calculation_frequency", 2)
        self.declare_parameter("declare_target_loc", True)
        self.declare_parameter("device_name", "CPU")
        self.tbot_odom_topic_name_ = self.get_parameter("tbot_odom_topic_name").value
        self.gbot_odom_topic_name_ = self.get_parameter("gbot_odom_topic_name").value
        self.audio_command_topic_name_ = self.get_parameter("audio_command_topic_name").value
        self.gesture_topic_name_ = self.get_parameter("gesture_topic_name").value
        self.motor_state_topic_name_ = self.get_parameter("motor_state_topic_name").value
        self.target_loc_topic_name_ = self.get_parameter("target_loc_topic_name").value
        self.audio_play_period_ = 1.0/self.get_parameter("audio_play_frequency").value
        self.distance_calcualtion_period_ = 1.0/self.get_parameter("distance_calculation_frequency").value
        self.declare_target_loc_ = self.get_parameter("declare_target_loc").value
        self.device_name_ = self.get_parameter("device_name").value
        self.device_name_ = self.device_name_.upper()
        if self.device_name_ not in ["CPU", "GPU", "NPU"]:
            self.device_name_ = "CPU"
        self.get_logger().info("using device: {}".format(self.device_name_))
        # audio and gesture subscriber
        self.audio_subscriber_ = self.create_subscription(AudioCommand, self.audio_command_topic_name_, self.audio_topic_callback, 10)
        self.gesture_subscriber_ = self.create_subscription(GestureCategory, self.gesture_topic_name_, self.gesture_topic_callback, 10)
        # odom subscriber for the tbot and guidebot
        self.tbot_odom_subscriber_ = self.create_subscription(Odometry, self.tbot_odom_topic_name_, self.tbot_odom_topic_callback, 10)
        self.gbot_odom_subscriber_ = self.create_subscription(Odometry, self.gbot_odom_topic_name_, self.gbot_odom_topic_callback, 10)
        # motor state and target_loc subscriber from adbscan
        self.motor_state_subscriber_ = self.create_subscription(Bool, self.motor_state_topic_name_, self.motor_state_topic_callback, 10)
        self.target_loc_subscriber_ = self.create_subscription(Point, self.target_loc_topic_name_, self.target_loc_topic_callback, 10)
        # timers for calculating tbot-gbot distance and playing converted audio
        self.audio_timer_ = self.create_timer(self.audio_play_period_, self.play_audio)
        self.distance_timer_ = self.create_timer(self.distance_calcualtion_period_, self.calculate_distance)
        # Loading melGAN model
        self.melgan_model_file_ = os.path.join(get_package_share_directory('text_to_speech_pkg'), 'config','model_files','text-to-speech-en-0001-generation.xml')
        ie = IECore()
        self.vocoder = MelGANIE(self.melgan_model_file_, ie, device=self.device_name_)
        # Loading model parameter files
        self.model_duration_file_ = os.path.join(get_package_share_directory('text_to_speech_pkg'), 'config','model_files','text-to-speech-en-0001-duration-prediction.xml')
        self.model_forward_file_ = os.path.join(get_package_share_directory('text_to_speech_pkg'), 'config','model_files','text-to-speech-en-0001-regression.xml')
        self.forward_tacotron = ForwardTacotronIE(self.model_duration_file_, self.model_forward_file_, ie, verbose=False, device=self.device_name_)
        self.speaker_emb = None
        if self.forward_tacotron.has_speaker_embeddings():
            self.speaker_emb = self.forward_tacotron.get_speaker_embeddings()[19, :]
        self.tbot_pos_ = [0.0, 0.0, 0.0]
        self.gbot_pos_ = [np.inf, 0.0, 0.0]
        self.distance = np.inf # distance between gbot and tbot
        self.target_distance = np.inf
        self.audio_command = ""
        self.gesture_command = ""
        self.motor_initiated = False
        self.played_audio_command = False
        self.played_gesture_command = False
        self.played_distance_info = False
        self.get_logger().info("text_to_speech_node has been started")

    def save_wavefile(self, x, path):
        sr = 22050
        with wave.open(path, "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(x.tobytes())

    def motor_state_topic_callback(self, motor_state_msg):
        self.motor_initiated = motor_state_msg.data
        if self.declare_target_loc_ and not self.motor_initiated:
            self.played_distance_info = False

    def target_loc_topic_callback(self, target_loc_msg):
        self.target_distance = np.sqrt(target_loc_msg.x*target_loc_msg.x + target_loc_msg.y*target_loc_msg.y)


    def tbot_odom_topic_callback(self, odom_msg):
        self.tbot_pos_ = [odom_msg.pose.pose.position.x, odom_msg.pose.pose.position.y, odom_msg.pose.pose.position.z]
    
    def gbot_odom_topic_callback(self, odom_msg):
        self.gbot_pos_ = [odom_msg.pose.pose.position.x, odom_msg.pose.pose.position.y, odom_msg.pose.pose.position.z]
    
    def calculate_distance(self):
        x = self.tbot_pos_[0]-self.gbot_pos_[0]
        y = self.tbot_pos_[1]-self.gbot_pos_[1]
        self.distance = np.sqrt(x*x + y*y)
        # print("distance between tbot and guide robot : ", self.distance)
        

    def audio_topic_callback(self, msg):
        if msg.audio_command != "no_action":
            self.audio_command = msg.audio_command       
        else:
            self.audio_command = ""
            self.played_audio_command = False

    def gesture_topic_callback(self, msg):
        if msg.gesture_category != "No_Action":
            if msg.gesture_category == "Thumb_Down":
                self.gesture_command = "thumbs down"
            elif msg.gesture_category == "Thumb_Up":
                self.gesture_command = "thumbs up"
            else:
                self.gesture_command = " ".join(msg.gesture_category.split("_")).lower()
        else:
            self.gesture_command = ""
            self.played_gesture_command = False
        
    def play_audio(self):
        audio_res = np.array([], dtype=np.int16)
        len_th = 512
        lines = []
        if self.audio_command!= "" and not self.played_audio_command:
            lines.append("Detected audio command: " + self.audio_command)
            self.played_audio_command = True
        if self.gesture_command != "" and not self.played_gesture_command:
            lines.append("Detected gesture: " + self.gesture_command)
            self.played_gesture_command = True
        if self.declare_target_loc_ and self.motor_initiated and not self.played_distance_info:
            lines.append("Target located at " + str(np.round(self.target_distance, 2)) + " meters")
            self.played_distance_info = True

        if len(lines) != 0:
            for i,line in enumerate(lines):
                line = line.rstrip()
                print("\nProcess line {} with length {}.".format(i, len(line)))
                print(line)
                if len(line) > len_th:
                    texts = []
                    prev_begin = 0
                    delimiters = '.!?;:'
                    for i, c in enumerate(line):
                        if (c in delimiters and i - prev_begin > len_th) or i == len(line) - 1:
                            texts.append(line[prev_begin:i + 1])
                            prev_begin = i + 1
                else:
                    texts = [line]
                for text in tqdm(texts):
                    mel = self.forward_tacotron.forward(text, alpha=1.0, speaker_emb=self.speaker_emb)
                    audio = self.vocoder.forward(mel)
                    audio_res = np.append(audio_res, audio)
            wave_obj = sa.WaveObject(audio_res.tobytes(), num_channels=1, bytes_per_sample=2, sample_rate=22050)
            play_obj = wave_obj.play()   # Audio is played from device
            play_obj.wait_done()


def main(args=None):
    rclpy.init(args= args)
    node = text_to_speech()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()
    