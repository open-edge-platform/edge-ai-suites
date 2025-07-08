from queue import Queue

import numpy as np
import pyaudio

from da import config
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class MicReceiver(PipelineWorker):
    np_dtype_map = {
        16: np.int16,
    }

    pyaudio_dtype_map = {
        16: pyaudio.paInt16,
    }

    def __init__(self, output_queue: Queue):
        """
        Initializes the MicReceiver.

        :param output_queue: Queue to send the audio chunks to.
        """
        super().__init__(self.__class__.__name__, WorkerType.Thread)

        self.output_queue = output_queue
        self.audio = pyaudio.PyAudio()

    def _init(self):
        pass

    def _run(self):
        stream = self.audio.open(
            input=True,
            channels=config.mic.channels,
            format=self.pyaudio_dtype_map[config.mic.bits],
            rate=config.mic.rate,
            frames_per_buffer=config.mic.chunk_size,
        )

        while self._is_running():
            try:
                data = stream.read(config.mic.chunk_size, exception_on_overflow=False)
                data = np.frombuffer(data, dtype=self.np_dtype_map[config.mic.bits]) / 32767
                self.output_queue.put(data)
            except Exception as e:
                logger.error(f"Could not read audio from mic: {e}")
                break
