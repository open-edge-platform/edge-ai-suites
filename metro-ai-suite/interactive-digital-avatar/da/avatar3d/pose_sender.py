import json
from copy import deepcopy
from queue import Queue, Empty

import numpy as np
import socketio

from da.avatar3d.body_pose_selector import select_random_pose
from da.avatar3d.face_data_util import npy_to_face_pose, merge_mouth_json
from da.util.da_time import RateLimiter
from da.util.woker import PipelineWorker, WorkerType


class PoseSender(PipelineWorker):
    def __init__(self, mouth_pose_input_queue: Queue, sio_addr: str, pose_sync_fps: int):

        self.mouth_pose_input_queue = mouth_pose_input_queue
        self.pose_sync_fps = pose_sync_fps
        self.sio_addr = sio_addr

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        self.rate_limiter = RateLimiter(self.pose_sync_fps)

        self.sio = socketio.Client()
        self.sio.connect(self.sio_addr)

        self.body_frame_idx = 0
        self.body_pose = []

        self.idle_face_frame_idx = 0
        idle_face_pose_npy = np.load("resource/avatar3d/idle_face.npy")
        self.idle_face_pose = npy_to_face_pose(idle_face_pose_npy)

    def _run(self):
        while self._is_running():
            try:
                speaking_mouth_pose = self.mouth_pose_input_queue.get_nowait()
            except Empty:
                speaking_mouth_pose = None

            body_pose = self.get_current_frame_body_pose(speaking_mouth_pose)
            face_pose = self.get_current_frame_face_pose(speaking_mouth_pose)
            merged_posed = self.merge_body_and_face_pose(body_pose, face_pose)
            self.send_current_frame_pose(merged_posed)

            self.rate_limiter.wait()

    def get_current_frame_body_pose(self, speaking_mouth_pose):
        # random select a pose according to current state
        if self.body_frame_idx >= len(self.body_pose):
            is_speaking = speaking_mouth_pose is not None
            random_pose = select_random_pose(is_speaking)
            self.body_pose = random_pose
            self.body_frame_idx = 0

        body = self.body_pose[self.body_frame_idx]
        self.body_frame_idx += 1
        body = deepcopy(body)

        return body

    def get_current_frame_face_pose(self, speaking_mouth_pose):
        if self.idle_face_frame_idx >= len(self.idle_face_pose):
            self.idle_face_frame_idx = 0

        face = self.idle_face_pose[self.idle_face_frame_idx]
        self.idle_face_frame_idx += 1
        face = deepcopy(face)

        # replace the idle mouth with speaking mouth
        if speaking_mouth_pose is not None:
            face = merge_mouth_json(face, speaking_mouth_pose)

        return face

    def merge_body_and_face_pose(self, body_pose, face_pose) -> dict:
        face_pose['face_data']['Bone'] = body_pose['huazhibing_default']['Bone']
        return face_pose

    def send_current_frame_pose(self, frame_pose: dict):
        frame_pose = json.dumps(frame_pose)
        send_data = {"name": "FaceData", "text": '0|' + frame_pose.strip()}
        self.sio.emit("cmd", send_data)
