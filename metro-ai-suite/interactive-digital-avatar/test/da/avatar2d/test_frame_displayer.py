import time
from queue import Queue

import cv2

from da.avatar2d.frame_displayer import FrameDisplayer


def test():
    queue = Queue()
    disp = FrameDisplayer(fps=24, frame_input_queue=queue)
    disp.start()

    cap = cv2.VideoCapture("input/video.mp4")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        queue.put(frame)

    time.sleep(3)
    disp.stop()


if __name__ == '__main__':
    test()
