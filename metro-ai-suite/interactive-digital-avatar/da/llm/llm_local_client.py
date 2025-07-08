from abc import ABC, abstractmethod
from concurrent.futures.thread import ThreadPoolExecutor
from queue import Queue
from typing import Generator

import openvino_genai

from da.llm.llm_base import LLMBaseClient
from da.util.log import logger


class LLMLocalClient(LLMBaseClient, ABC):
    def __init__(self, ov_model_dir: str, ov_device: str, max_tokens):
        """
        Initialize the OV LLM model from model dir.
        """
        self.ov_model_dir = ov_model_dir
        self.ov_device = ov_device
        self.max_tokens = max_tokens
        self.pipe = openvino_genai.LLMPipeline(ov_model_dir, ov_device)
        self.executor = ThreadPoolExecutor()
        logger.info(f"Load local LLM from {self.ov_model_dir}")

    @abstractmethod
    def apply_prompt_template(self, prompt: str) -> str:
        pass

    def generate_text(self, prompt: str) -> Generator[str, None, None]:
        text_queue = Queue()

        def text_streamer(text):
            text_queue.put(text)

        input_text = self.apply_prompt_template(prompt)
        generation_kwargs = dict(
            inputs=input_text, streamer=text_streamer, max_new_tokens=self.max_tokens,
            do_sample=True, temperature=0.8, top_p=0.9, top_k=5
        )
        req = self.executor.submit(self.pipe.generate, **generation_kwargs)

        while not req.done() or not text_queue.empty():
            yield text_queue.get()

        req.result()
