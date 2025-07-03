from queue import Queue

from da.listen.mic_receiver import MicReceiver
from da.util.log import logger


def test():
    output_queue = Queue()
    mic_receiver = MicReceiver(output_queue)
    mic_receiver.start()
    for _ in range(4):
        chunk = output_queue.get()
        logger.info(f"Received audio chunk of size {len(chunk)}")
    mic_receiver.stop()


if __name__ == '__main__':
    test()
