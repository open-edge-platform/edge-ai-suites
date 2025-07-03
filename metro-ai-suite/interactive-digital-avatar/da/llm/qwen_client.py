import json
from typing import Generator

from da import config
from da.llm.llm_local_client import LLMLocalClient
from da.llm.llm_remote_client import LLMRemoteClient


class QwenRemoteClient(LLMRemoteClient):

    def __init__(self):
        super().__init__(config.qwen.remote.base_url)

    def generate_text(self, prompt: str) -> Generator[str, None, None]:
        payload = {
            "query": prompt,
            "db_name": "chroma",
            "table": "digital_zh",
            "top_k": 1,
            "distance": 300,
            "stream": True,
            "model_name": "Qwen2-7B-Instruct",
            "temperature": 0.7,
            "max_tokens": 0,
            "prompt_name": "default_cn"
        }

        for chunk in self.send_request(payload):
            res_json = chunk.split("data:")[1]
            res = json.loads(res_json)
            yield res["answer"]

    def generate_text_complete_sentences(self, prompt: str) -> Generator[str, None, None]:
        return super()._generate_text_complete_sentences(prompt, 10, {'、', '，', '。', '！', '？'})


class QwenLocalClient(LLMLocalClient):

    def __init__(self):
        self.prompt_template = ("<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                                "Cutting Knowledge Date: December 2023\n"
                                "Today Date: 26 Jul 2024\n\n"
                                "你的名字叫小智，是一个部署在英特尔边缘设备上的人工智能助手。"
                                "请用中文简要地回答用户的问题。<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
                                "%s<|eot_id|><|start_header_id|>assistant<|eot_id|>\n\n")

        super().__init__(config.qwen.local.ov_model_dir, config.ov.device, config.qwen.local.max_tokens)

    def apply_prompt_template(self, prompt: str) -> str:
        return self.prompt_template % prompt

    def generate_text_complete_sentences(self, prompt: str) -> Generator[str, None, None]:
        return super()._generate_text_complete_sentences(prompt, 10, {'、', '，', '。', '！', '？'})
