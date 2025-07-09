import time

import keyboard

from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class KeyboardWatcher(PipelineWorker):
    record_key = 'L'

    def __init__(self):
        super().__init__(self.__class__.__name__, WorkerType.Thread)
        self._record_key_pressed = False

    def is_recording(self):
        return self._record_key_pressed

    def _init(self):
        pass

    def _run(self):
        while self._is_running():
            if keyboard.is_pressed(self.record_key):
                if not self._record_key_pressed:
                    self._record_key_pressed = True
                    logger.info(f"Record key '{self.record_key}' pressed")
            else:
                if self._record_key_pressed:
                    self._record_key_pressed = False
                    logger.info(f"Record key '{self.record_key}' released")

            time.sleep(0.1)
