from collections import deque
from queue import Queue

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from da import config
from da.listen.asr_client import AsrClient
from da.listen.mic_receiver import MicReceiver
from da.util.log import logger


def test():
    original_sample_rate, data = wavfile.read("resource/test/test_audio.wav")
    data = resample_poly(data, config.mic.rate, original_sample_rate)
    data = np.float32(data / np.max(np.abs(data)))

    asr_client = AsrClient()
    text = asr_client.recognize(data)
    logger.info(text)


def use_mic_input():
    audio_queue = Queue()
    mic_receiver = MicReceiver(audio_queue)
    mic_receiver.start()

    chunks_per_size = int(config.mic.rate / config.mic.chunk_size)
    buffer_size = 3 * chunks_per_size
    buffer = deque(maxlen=buffer_size)

    idx = 0
    asr_client = AsrClient()
    while True:
        idx += 1
        buffer.append(audio_queue.get())
        if idx % chunks_per_size == 0:
            text = asr_client.recognize(np.concatenate(buffer))
            logger.info(text)


if __name__ == '__main__':
    # test()
    use_mic_input()
