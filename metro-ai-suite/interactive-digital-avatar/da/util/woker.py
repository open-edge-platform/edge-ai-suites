import multiprocessing
import signal
import threading
import traceback
from abc import ABC, abstractmethod
from enum import Enum

from da.util.log import logger


class WorkerType(Enum):
    Thread = "Thread"
    Process = "Process"


class PipelineWorker(ABC):
    def __init__(self, name: str, worker_type: WorkerType) -> None:
        self.name = name
        self.worker_type = worker_type
        self._running = False

        if worker_type == WorkerType.Thread:
            self._worker = threading.Thread(target=self._init_and_run, name=self.name)
            self._init_event = threading.Event()
            self._start_event = threading.Event()
            self._stop_event = threading.Event()
        elif worker_type == WorkerType.Process:
            self._worker = multiprocessing.Process(target=self._init_and_run, name=self.name)
            self._init_event = multiprocessing.Event()
            self._start_event = multiprocessing.Event()
            self._stop_event = multiprocessing.Event()

        self._worker.start()

    def start(self):
        """
        Starts the worker by creating a thread or process and running the `run()` method.
        """
        if not self._is_running():
            self._init_event.wait()
            self._start_event.set()
        else:
            stack = traceback.format_stack()
            logger.warning("Worker already started. Duplicate call for start(). \n" + "".join(stack))

    def stop(self):
        """
        Stops the worker if it is running.
        """
        if self._is_running():
            self._start_event.clear()
            self._stop_event.set()
            self._worker.join()
        else:
            stack = traceback.format_stack()
            logger.warning("Worker already stopped. Duplicate call for stop(). \n" + "".join(stack))

    def _is_running(self) -> bool:
        return self._start_event.is_set()

    def _init_and_run(self):
        # We ignore ctrl+c in sub-process. By this way,
        # the sub-thread worker in sub-process could end.
        if self.worker_type == WorkerType.Process:
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        self._init()
        self._init_event.set()
        logger.info(f"{self.worker_type.value} {self.name} init.")
        self._start_event.wait()
        logger.info(f"{self.worker_type.value} {self.name} started.")
        self._run()
        logger.info(f"{self.worker_type.value} {self.name} finished.")

    @abstractmethod
    def _init(self):
        """
        This method should be implemented by driven classes.
        It defines the init steps before run() calls.
        """
        pass

    @abstractmethod
    def _run(self):
        """
        This method should be implemented by driven classes.
        It defines the work the worker will perform.
        """
        pass
