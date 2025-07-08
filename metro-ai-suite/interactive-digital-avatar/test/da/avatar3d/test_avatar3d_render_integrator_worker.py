import time
from queue import Queue

from da.avatar3d.render_integrator import RenderIntegrator
from da.util.log import logger


def test():
    queue = Queue(1)
    avatar = RenderIntegrator(queue)
    avatar.start()
    queue.put("resource/test/test_audio.wav")
    logger.info("Put audio into queue")
    time.sleep(5)
    avatar.stop()


if __name__ == '__main__':
    test()
