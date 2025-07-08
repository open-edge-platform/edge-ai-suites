from multiprocessing import Queue

from da.speak.audio_player import AudioPlayer


def test():
    queue = Queue(1)
    ap = AudioPlayer(queue)
    ap.start()

    for _ in range(4):
        queue.put("resource/test/test_audio.wav")

    ap.stop()


if __name__ == '__main__':
    test()
