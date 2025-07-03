from multiprocessing import Queue as p_Queue
from queue import Queue, Empty

from da.util.woker import PipelineWorker, WorkerType


class AVSyncer(PipelineWorker):
    def __init__(
            self,
            lip_input_queue: Queue,
            lip_output_queue: Queue,
            audio_input_queue: Queue,
            audio_output_queue: p_Queue
    ):

        self.lip_input_queue = lip_input_queue
        self.lip_output_queue = lip_output_queue
        self.audio_input_queue = audio_input_queue
        self.audio_output_queue = audio_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        while self._is_running():
            try:
                audio_path, lips_len = self.audio_input_queue.get(timeout=1)
            except Empty:
                continue

            self.audio_output_queue.put(audio_path)
            for _ in range(lips_len):
                chunks = self.lip_input_queue.get()
                self.lip_output_queue.put(chunks)
