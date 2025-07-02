from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class TestWorkerThread(PipelineWorker):
    def __init__(self):
        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        """
        Simple implementation of the `run` method for testing.
        logger.infos a message every second until stopped.
        """
        import time

        while self._is_running():
            logger.info(f"TestWorkerThread is working...")
            time.sleep(1)  # Simulate work


class TestWorkerProcess(PipelineWorker):
    def __init__(self):
        super().__init__(self.__class__.__name__, WorkerType.Process)

    def _init(self):
        pass

    def _run(self):
        """
        Simple implementation of the `run` method for testing.
        logger.infos a message every second until the stop event is set.
        """
        import time

        while self._is_running():
            logger.info(f"TestWorkerProcess is working...")
            time.sleep(1)  # Simulate work


def test_thread():
    import time

    # Create and start the test worker thread
    worker_thread = TestWorkerThread()
    worker_thread.start()

    # Let it run for a few seconds
    time.sleep(5)
    worker_thread.stop()


def test_process():
    import time

    # Create and start the test worker process
    worker_process = TestWorkerProcess()
    worker_process.start()

    # Let it run for a few seconds
    time.sleep(5)
    worker_process.stop()


if __name__ == '__main__':
    test_thread()
    test_process()
