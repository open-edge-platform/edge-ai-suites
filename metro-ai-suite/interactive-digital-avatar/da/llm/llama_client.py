import json
from typing import Generator

from da import config
from da.llm.llm_remote_client import LLMRemoteClient


class LlamaRemoteClient(LLMRemoteClient):

    def __init__(self):
        super().__init__(config.llama.base_url)

    def generate_text(self, prompt: str) -> Generator[str, None, None]:
        payload = {
            "question": prompt,
            "max_tokens": 512,
            "model": "Llama3_1_8B_Instruct"
        }

        for chunk in self.send_request(payload):
            res_json = chunk.split("data:")[1]
            res = json.loads(res_json)
            yield res["answer"]

    def generate_text_complete_sentences(self, prompt: str) -> Generator[str, None, None]:
        return super()._generate_text_complete_sentences(prompt, 10, {'、', '，', '。', '！', '？'})
