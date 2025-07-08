from collections import deque
from enum import Enum, auto
from queue import Empty, Queue

import numpy as np

from da import config
from da.listen.asr_client import AsrClient
from da.listen.keyboard_watcher import KeyboardWatcher
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType


class AsrState(Enum):
    Standby = auto()  # detecting wake words
    ManualRecognizing = auto()  # tigger by keyboard
    AutoRecognizing = auto()  # tigger by wake words


class AsrWorker(PipelineWorker):
    max_buffer_secs = 3  # keep last 3 secs audio in the buffer
    min_asr_interval_secs = 0.5  # the min interval between two asr inference (wake words or silent detection)
    silent_detect_secs = 0.5  # the time threshold to end AutoRecognizing that mic input keep silent
    silence_threshold = 0.001  # 0 means absolute silent while 1 means absolute loud.
    min_question_secs = 2  # the min length of question after wake word.

    def __init__(
            self,
            audio_input_queue: Queue,
            text_output_queue: Queue,
            keyboard_watcher: KeyboardWatcher,
            audio_output_queue_to_player: Queue,
            hello_audio_path: str,
    ):

        self.audio_input_queue = audio_input_queue
        self.text_output_queue = text_output_queue
        self.keyboard_watcher = keyboard_watcher
        self.audio_output_queue_to_player = audio_output_queue_to_player
        self.hello_audio_path = hello_audio_path

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        self.asr_client = AsrClient()

        buffers_per_sec = config.mic.rate / config.mic.chunk_size
        self.standby_buffer_size = int(self.max_buffer_secs * buffers_per_sec)
        self.silent_buffer_size = int(self.silent_detect_secs * buffers_per_sec)
        self.min_asr_size = int(self.min_asr_interval_secs * buffers_per_sec)
        self.min_question_size = int(self.min_question_secs * buffers_per_sec)
        self.chunks_received = 0

        self.state = AsrState.Standby
        self.recognize_buffer = list()
        self.standby_buffer = deque(maxlen=self.standby_buffer_size)

    def _run(self):
        while self._is_running():
            try:
                audio_data = self.audio_input_queue.get(timeout=1)
                self.chunks_received += 1
            except Empty:
                continue

            if self.state == AsrState.Standby:
                self.standby(audio_data)
            elif self.is_recognizing():
                self.recognize(audio_data)

    def is_recognizing(self):
        return self.state in (AsrState.ManualRecognizing, AsrState.AutoRecognizing)

    def standby(self, audio_data):
        assert self.state == AsrState.Standby

        self.standby_buffer.append(audio_data)

        if self.manual_recognize_started():
            self.state = AsrState.ManualRecognizing
            self.say_hello()
            return

        if self.auto_recognize_started():
            self.state = AsrState.AutoRecognizing
            self.say_hello()
            return

    def manual_recognize_started(self) -> bool:
        if self.state != AsrState.Standby:
            return False

        if self.keyboard_watcher.is_recording():
            self.recognize_buffer.extend(self.standby_buffer)
            self.standby_buffer.clear()
            return True

        return False

    def auto_recognize_started(self) -> bool:
        if self.state != AsrState.Standby:
            return False

        if self.chunks_received % self.min_asr_size == 0:
            audio_input = np.concatenate(self.standby_buffer)
            if self.is_silent(audio_input):
                return False

            text = self.asr_client.recognize(audio_input)
            logger.info(f"Standby ASR: {text}")

            for word in config.wake.wake_words:
                # Trigger by wake words
                if word in text:
                    logger.info(f"Wake by word: {word}")
                    self.recognize_buffer.extend(self.standby_buffer)
                    self.standby_buffer.clear()
                    return True

        return False

    def say_hello(self):
        self.audio_output_queue_to_player.put(self.hello_audio_path)

    def recognize(self, audio_data):
        assert self.is_recognizing()
        self.recognize_buffer.append(audio_data)

        if self.manual_recognize_ended():
            self.state = AsrState.Standby
            return

        if self.auto_recognize_ended():
            self.state = AsrState.Standby
            return

    def manual_recognize_ended(self) -> bool:
        if self.state != AsrState.ManualRecognizing:
            return False

        if not self.keyboard_watcher.is_recording():
            self.end_recognize()
            return True

        return False

    def auto_recognize_ended(self) -> bool:
        if self.state != AsrState.AutoRecognizing:
            return False

        # recognize_buffer = standby_buffer + questions_buffer
        if len(self.recognize_buffer) < self.standby_buffer_size + self.min_question_size:
            return False

        # End by mic silent input
        if self.chunks_received % self.min_asr_size == 0:
            silent_buffer = np.concatenate(self.recognize_buffer[-self.silent_buffer_size:])
            if self.is_silent(silent_buffer):
                self.end_recognize()
                return True

        return False

    @classmethod
    def is_silent(cls, audio_data: np.ndarray):
        # Compute the average amplitude in the chunk
        average_amplitude = np.mean(np.abs(audio_data))

        # Check if the average amplitude is below the silence threshold
        return average_amplitude < cls.silence_threshold

    def end_recognize(self):
        audio_input = np.concatenate(self.recognize_buffer)
        text = self.asr_client.recognize(audio_input)

        # remove contents before wake words from text
        for word in config.wake.wake_words:
            if word in text:
                text = text[text.find(word) + len(word):]
                break

        # skip empty question
        if len(text.strip()) > 0:
            logger.info(f"Question from ASR: {text}")
            self.text_output_queue.put(text)

        self.recognize_buffer.clear()
