from queue import Queue, Empty

from da.util.woker import PipelineWorker, WorkerType


class AVSyncer(PipelineWorker):
    def __init__(
            self,
            chunk_input_queue: Queue,
            chunk_output_queue: Queue,
            audio_input_queue: Queue,
            audio_output_queue: Queue
    ):

        self.chunk_input_queue = chunk_input_queue
        self.chunk_output_queue = chunk_output_queue
        self.audio_input_queue = audio_input_queue
        self.audio_output_queue = audio_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        while self._is_running():
            try:
                audio_path, chunks_size = self.audio_input_queue.get(timeout=1)
            except Empty:
                continue

            self.audio_output_queue.put(audio_path)
            for _ in range(chunks_size):
                chunks = self.chunk_input_queue.get()
                self.chunk_output_queue.put(chunks)
