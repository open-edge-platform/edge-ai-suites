from pathlib import Path
from queue import Queue, Empty

from scipy.io import wavfile

from da.avatar3d.lip_sync_client import LipSyncClient
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class LipSyncWorker(PipelineWorker):
    def __init__(self, lip_sync_client: LipSyncClient, audio_input_queue: Queue, lip_output_queue: Queue, audio_output_queue: Queue):

        self.client = lip_sync_client
        self.audio_input_queue = audio_input_queue
        self.lip_output_queue = lip_output_queue
        self.audio_output_queue = audio_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        while self._is_running():
            try:
                audio_path = self.audio_input_queue.get(timeout=1)
            except Empty:
                continue

            if not Path(audio_path).exists():
                logger.error(f"{audio_path} not exist.")
                continue

            logger.info(f"Processing {audio_path}")
            fs, data = wavfile.read(audio_path)
            face_pose_with_synced_lip = self.client.predict(data, fs)
            logger.info(f"Get lip data from {audio_path}")

            self.audio_output_queue.put((audio_path, len(face_pose_with_synced_lip)))
            for pose in face_pose_with_synced_lip:
                self.lip_output_queue.put(pose)
