from multiprocessing import Queue

from da.speak.tts_worker import TTSWorker


def test():
    text_input_queue = Queue()
    audio_output_queue = Queue()

    tts_worker = TTSWorker(False, text_input_queue, audio_output_queue)
    tts_worker.start()

    for _ in range(10):
        text_input_queue.put("一二三四五，")

    for _ in range(3):
        audio_output_queue.get()

    tts_worker.stop()


if __name__ == '__main__':
    test()
