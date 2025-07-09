import math
from pathlib import Path
from queue import Queue, Empty

import numpy as np

from da.avatar2d.avatar_ov import AvatarOV
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class WhisperWorker(PipelineWorker):
    def __init__(self, avatar: AvatarOV, audio_input_queue: Queue, whisper_output_queue: Queue, audio_output_queue: Queue):

        self.avatar = avatar
        self.audio_input_queue = audio_input_queue
        self.audio_output_queue = audio_output_queue
        self.whisper_output_queue = whisper_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        def generate_batches(lst, batch_size):
            for i in range(0, len(lst), batch_size):
                yield lst[i:i + batch_size]

        while self._is_running():
            try:
                audio_path = self.audio_input_queue.get(timeout=1)
            except Empty:
                continue

            if not Path(audio_path).exists():
                logger.error(f"{audio_path} not exist.")
                continue

            logger.info(f"whisper predicting {audio_path}")
            whisper_chunks = self.avatar.audio2chunks(audio_path, self.avatar.fps)
            logger.info(f"whisper chunks from {audio_path}")

            chunks_size = math.ceil(len(whisper_chunks) / self.avatar.batch_size)
            self.audio_output_queue.put((audio_path, chunks_size))
            for chunks in generate_batches(whisper_chunks, self.avatar.batch_size):
                chunks = np.stack(chunks)
                self.whisper_output_queue.put(chunks)
