import time
from queue import Queue

import numpy as np

from da import config
from da.avatar3d.face_data_util import npy_to_face_pose
from da.avatar3d.pose_sender import PoseSender


def test():
    fake_speaking_mouth_pose_npy = np.load("resource/avatar3d/speaking_mouth.npy")[30:120]
    fake_speaking_mouth_pose = npy_to_face_pose(fake_speaking_mouth_pose_npy)

    mouth_queue = Queue(1)
    pose_sender = PoseSender(mouth_queue, config.avatar3d.sio_addr, config.avatar3d.pose_sync_fps)
    pose_sender.start()

    time.sleep(3)
    for pose in fake_speaking_mouth_pose:
        mouth_queue.put(pose)
    time.sleep(3)

    pose_sender.stop()


if __name__ == '__main__':
    test()
