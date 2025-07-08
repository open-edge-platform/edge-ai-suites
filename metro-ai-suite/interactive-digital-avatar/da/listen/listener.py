import multiprocessing
import queue

from da.listen.asr_worker import AsrWorker
from da.listen.keyboard_watcher import KeyboardWatcher
from da.listen.mic_receiver import MicReceiver
from da.util.woker import PipelineWorker, WorkerType


class Listener(PipelineWorker):
    def __init__(
            self,
            text_output_queue: multiprocessing.Queue,
            audio_output_queue_to_player: multiprocessing.Queue,
            hello_audio_path: str,
    ):
        self.text_output_queue = text_output_queue
        self.audio_output_queue_to_player = audio_output_queue_to_player
        self.hello_audio_path = hello_audio_path

        super().__init__(self.__class__.__name__, WorkerType.Process)

    def _init(self):
        self.audio_queue = queue.Queue()
        self.mic_receiver = MicReceiver(self.audio_queue)
        self.keyboard_watcher = KeyboardWatcher()
        self.asr_worker = AsrWorker(
            self.audio_queue,
            self.text_output_queue,
            self.keyboard_watcher,
            self.audio_output_queue_to_player,
            self.hello_audio_path
        )

    def _run(self):
        self.asr_worker.start()
        self.mic_receiver.start()
        self.keyboard_watcher.start()

        self._stop_event.wait()

        self.keyboard_watcher.stop()
        self.mic_receiver.stop()
        self.asr_worker.stop()
