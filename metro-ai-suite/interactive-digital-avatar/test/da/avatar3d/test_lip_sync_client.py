from scipy.io import wavfile

from da import config
from da.avatar3d.lip_sync_client import LipSyncClient


def test():
    ls = LipSyncClient(config.avatar3d.said_addr, config.avatar3d.said_fps, config.avatar3d.pose_sync_fps)
    fs, data = wavfile.read("resource/test/test_audio.wav")
    pose = ls.predict(data, fs)
    print(len(pose))


if __name__ == '__main__':
    test()
