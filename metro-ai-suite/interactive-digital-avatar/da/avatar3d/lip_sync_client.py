import json

import numpy as np
import pandas as pd
import requests
from scipy.interpolate import interp1d

from da.avatar3d.face_data_util import said_order_to_render_order, npy_to_face_pose
from da.util.log import logger


class LipSyncClient:
    def __init__(self, said_addr: str, said_fps: int, pose_sync_fps: int):
        self.said_fps = said_fps
        self.said_addr = said_addr
        self.pose_sync_fps = pose_sync_fps

    def predict(self, audio_data: np.array, sample_rate: int):
        data = self.normalize_audio(audio_data)
        said_data = json.dumps({"audio": data.tolist(), "audio_fs": sample_rate})
        logger.info("Sending audio frames to siad server.")
        said_response = requests.post(self.said_addr, json=said_data)
        if said_response.status_code != 200:
            logger.error(f"Failed to send audio to said server. {said_response.status_code}")
        else:
            logger.info("200 OK from said server")

        response_data = said_response.json()
        face_data_said = np.array(response_data["arkit_points"])
        face_data_said = self.postprocess_said(face_data_said)
        face_data_said = self.resample_to_fps(face_data_said, self.said_fps, self.pose_sync_fps)
        face_data_said = said_order_to_render_order(face_data_said)
        face_data_said = npy_to_face_pose(face_data_said)
        return face_data_said

    def normalize_audio(self, data):
        # Check the data type to normalize accordingly
        if data.dtype == np.int16:
            # 16-bit PCM: max value is 32768
            data = data / 32768.0
        elif data.dtype == np.int32:
            # 32-bit PCM: max value is 2147483648
            data = data / 2147483648.0
        elif data.dtype == np.uint8:
            # 8-bit PCM: convert from unsigned [0, 255] to signed [-1, 1]
            data = (data - 128) / 128.0
        elif data.dtype == np.float32 or data.dtype == np.float64:
            # Float PCM: assume it's already in [-1, 1] range, so no scaling is needed
            pass
        else:
            raise ValueError("Unsupported audio format")

        return data

    def postprocess_said(self, face_data_group):
        df = pd.DataFrame(face_data_group)
        num_rows = df.shape[0]
        new_cols_start = pd.DataFrame(np.zeros((num_rows, 14)), columns=[f'new_col_{i + 1}' for i in range(14)])
        new_cols_end = pd.DataFrame(np.zeros((num_rows, 5)), columns=[f'new_col_{i + 15}' for i in range(5)])
        df = pd.concat([new_cols_start, df], axis=1)
        df = pd.concat([df.iloc[:, :41], new_cols_end, df.iloc[:, 41:]], axis=1)
        data_array = df.to_numpy()
        return data_array * 1.2

    def resample_to_fps(self, data, original_fps, target_fps):
        # Calculate original and target timestamps
        num_samples = data.shape[0]
        original_timestamps = np.linspace(0, num_samples / original_fps, num_samples)
        target_timestamps = np.linspace(0, num_samples / original_fps, int(num_samples * target_fps / original_fps))

        # Create an interpolation function and apply it
        interpolator = interp1d(original_timestamps, data, axis=0, kind='linear')
        resampled_data = interpolator(target_timestamps)

        return resampled_data
