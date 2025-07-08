from queue import Queue, Empty

import cv2

from da.util.da_time import RateLimiter
from da.util.woker import PipelineWorker, WorkerType


class FrameDisplayer(PipelineWorker):
    def __init__(self, fps: int, frame_input_queue: Queue):

        self.fps = fps
        self.frame_input_queue = frame_input_queue
        self.window_name = "2D Digital Avatar"

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        self.rate_limiter = RateLimiter(self.fps)

    def _run(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)

        while self._is_running():
            try:
                img = self.frame_input_queue.get(timeout=1)
            except Empty:
                continue

            cv2.imshow(self.window_name, img)
            cv2.waitKey(1)

            self.rate_limiter.wait()

        cv2.destroyWindow(self.window_name)
