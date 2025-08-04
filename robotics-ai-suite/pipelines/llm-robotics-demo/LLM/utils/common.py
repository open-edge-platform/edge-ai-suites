# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import cv2
import io
import numpy as np
from scipy.io import wavfile

def draw_rect(image, coordinates=[0, 0, 50, 50], color=(0, 0, 255), thickness=2):
    start_point = (int(coordinates[0]), int(coordinates[1]))
    end_point = (int(coordinates[2]), int(coordinates[3]))
    cv2.rectangle(image, start_point, end_point, color, thickness)

def draw_points(orig_img, coordinates, radius=1, color=(0, 0, 255), thickness=2):
    orig_img = cv2.circle(orig_img, coordinates, radius, color, thickness)
    return orig_img

def resample(audio, src_sample_rate, dst_sample_rate):
    """
    Resample audio to specific sample rate

    Parameters:
      audio: input audio signal
      src_sample_rate: source audio sample rate
      dst_sample_rate: destination audio sample rate
    Returns:
      resampled_audio: input audio signal resampled with dst_sample_rate
    """
    if src_sample_rate == dst_sample_rate:
        return audio
    duration = audio.shape[0] / src_sample_rate
    resampled_data = np.zeros(shape=(int(duration * dst_sample_rate)), dtype=np.float32)
    x_old = np.linspace(0, duration, audio.shape[0], dtype=np.float32)
    x_new = np.linspace(0, duration, resampled_data.shape[0], dtype=np.float32)
    resampled_audio = np.interp(x_new, x_old, audio)
    return resampled_audio.astype(np.float32)

def audio_to_float(audio):
    """
    convert audio signal to floating point format
    """
    return audio.astype(np.float32) / np.iinfo(audio.dtype).max

def preprocess_wav_file(input_audio_file):
    sample_rate, audio = wavfile.read(
        io.BytesIO(open(input_audio_file, 'rb').read()))
    audio = audio_to_float(audio)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    # The model expects mono-channel audio with a 16000 Hz sample rate, represented in floating point range. When the
    # audio from the input video does not meet these requirements, we will need to apply preprocessing.
    resample_rate = 16000
    resampled_audio = resample(audio, sample_rate, resample_rate)
    return resampled_audio, resample_rate