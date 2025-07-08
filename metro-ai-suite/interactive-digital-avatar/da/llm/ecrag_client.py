import json
from typing import Generator

from da import config
from da.llm.llm_remote_client import LLMRemoteClient


class ECRAGRemoteClient(LLMRemoteClient):

    def __init__(self):
        super().__init__(config.ecrag.base_url)

    def generate_text(self, prompt: str) -> Generator[str, None, None]:
        payload = {
            "messages": prompt,
            "stream": True
        }

        return self.send_request(payload, iter_line=False)

    def generate_text_complete_sentences(self, prompt: str) -> Generator[str, None, None]:
        return super()._generate_text_complete_sentences(prompt, 10, {'、', '，', '。', '！', '？'})
