import time
from queue import Queue, Empty

from da import config
from da.avatar3d.lip_sync_client import LipSyncClient
from da.avatar3d.lip_sync_worker import LipSyncWorker
from da.util.log import logger


def test():
    audio_input_queue = Queue(1)
    audio_output_queue = Queue(1)
    lip_output_queue = Queue(1)

    ls = LipSyncClient(config.avatar3d.said_addr, config.avatar3d.said_fps, config.avatar3d.pose_sync_fps)
    lip_syncer = LipSyncWorker(ls, audio_input_queue, lip_output_queue, audio_output_queue)
    lip_syncer.start()

    time.sleep(1)
    audio_input_queue.put("resource/test/test_audio.wav")
    audio_path = audio_output_queue.get()
    assert audio_path[0] == "resource/test/test_audio.wav"

    try:
        while True:
            lip_data = lip_output_queue.get(timeout=1)
            logger.info(lip_data)
    except Empty:
        pass

    time.sleep(1)
    lip_syncer.stop()


if __name__ == '__main__':
    test()
