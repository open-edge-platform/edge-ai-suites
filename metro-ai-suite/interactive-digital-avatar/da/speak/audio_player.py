from multiprocessing import Queue
from pathlib import Path
from queue import Empty

from playsound import playsound

from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class AudioPlayer(PipelineWorker):
    def __init__(self, input_queue: Queue):

        self.input_queue = input_queue

        super().__init__(self.__class__.__name__, WorkerType.Process)

    def _init(self):
        pass

    def _run(self):
        while self._is_running():
            try:
                audio_path = self.input_queue.get(timeout=1)
            except Empty:
                continue

            if not Path(audio_path).exists():
                logger.error(f"{audio_path} not exist.")
                continue

            logger.info(f"playing \"{audio_path}\"")
            playsound(str(Path(audio_path).absolute()))
