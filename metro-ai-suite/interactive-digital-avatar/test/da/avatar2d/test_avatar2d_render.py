import time
from multiprocessing import Queue

from da.avatar2d.render import AvatarRender


def test():
    queue = Queue(1)
    avatar = AvatarRender("my-avatar", 24, queue)
    avatar.start()
    queue.put("resource/test/test_audio.wav")
    time.sleep(10)
    avatar.stop()


if __name__ == '__main__':
    test()
