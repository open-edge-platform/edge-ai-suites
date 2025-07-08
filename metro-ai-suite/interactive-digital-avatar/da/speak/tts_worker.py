import queue
from multiprocessing import Queue

from da.speak.tts_client import TTSClient
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class TTSWorker(PipelineWorker):

    def __init__(self, tts_male: bool, text_input_queue: Queue, audio_output_queue: Queue):

        self.tts_male = tts_male
        self.text_input_queue = text_input_queue
        self.audio_output_queue = audio_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Process)

    def _init(self):
        self.tts_client = TTSClient(self.tts_male)

    def _run(self):
        while self._is_running():
            try:
                text = self.text_input_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                audio_path = self.tts_client.tts(text)
            except Exception as e:
                logger.exception(f"Error while tts {text}.")
                continue
            self.audio_output_queue.put(audio_path)
