import time
from multiprocessing import Queue

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from da import config
from da.listen.asr_worker import AsrWorker
from da.listen.keyboard_watcher import KeyboardWatcher
from da.listen.mic_receiver import MicReceiver
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class MockMicReceiver(PipelineWorker):
    def __init__(self, audio_output_queue: Queue):
        super().__init__(self.__class__.__name__, WorkerType.Thread)

        self.audio_output_queue = audio_output_queue

        # read test audio file
        original_sample_rate, data = wavfile.read("resource/test/test_audio.wav")
        data = resample_poly(data, config.mic.rate, original_sample_rate)
        data = np.float32(data / np.max(np.abs(data)))
        self.audio_data = data

    def _init(self):
        pass

    def _run(self):
        idx = 0
        while self._is_running():
            if idx < len(self.audio_data):
                self.audio_output_queue.put(self.audio_data[idx:idx + config.mic.chunk_size])
                idx += config.mic.chunk_size
            else:
                self.audio_output_queue.put(np.zeros(config.mic.chunk_size, dtype=np.int16))

            time.sleep(config.mic.chunk_size / config.mic.rate)


def test_trigger_by_keyboard():
    audio_input_queue = Queue()
    audio_output_queue = Queue()
    text_queue = Queue()
    keyboard_watcher = KeyboardWatcher()
    asr_worker = AsrWorker(audio_input_queue, text_queue, keyboard_watcher, audio_output_queue, config.tts.male_hello_wav)
    mock_mic = MockMicReceiver(audio_input_queue)

    asr_worker.start()
    mock_mic.start()
    keyboard_watcher.start()

    time.sleep(1)
    asr_worker.keyboard_watcher._record_key_pressed = True
    time.sleep(1)
    asr_worker.keyboard_watcher._record_key_pressed = False
    time.sleep(1)

    text_queue.get()
    audio_input_queue.get()

    keyboard_watcher.stop()
    mock_mic.stop()
    asr_worker.stop()


def test_trigger_by_wake_word():
    audio_input_queue = Queue()
    audio_output_queue = Queue()
    text_queue = Queue()
    keyboard_watcher = KeyboardWatcher()
    asr_worker = AsrWorker(audio_input_queue, text_queue, keyboard_watcher, audio_output_queue, config.tts.male_hello_wav)
    mock_mic = MockMicReceiver(audio_input_queue)

    asr_worker.start()
    mock_mic.start()
    keyboard_watcher.start()

    text_queue.get()

    keyboard_watcher.stop()
    mock_mic.stop()
    asr_worker.stop()


def use_mic_input():
    audio_input_queue = Queue()
    audio_output_queue = Queue()
    text_queue = Queue()
    keyboard_watcher = KeyboardWatcher()
    asr_worker = AsrWorker(audio_input_queue, text_queue, keyboard_watcher, audio_output_queue, config.tts.male_hello_wav)
    mic = MicReceiver(audio_input_queue)

    asr_worker.start()
    mic.start()
    keyboard_watcher.start()

    while True:
        try:
            logger.info(text_queue.get())
        except KeyboardInterrupt:
            break

    keyboard_watcher.stop()
    mic.stop()
    asr_worker.stop()


if __name__ == '__main__':
    test_trigger_by_keyboard()
    test_trigger_by_wake_word()
    # use_mic_input()
