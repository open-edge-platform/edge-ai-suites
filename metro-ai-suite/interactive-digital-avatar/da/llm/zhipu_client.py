import json
from typing import Generator

from da import config
from da.llm.llm_remote_client import LLMRemoteClient


class ZhipuRemoteClient(LLMRemoteClient):
    def __init__(self):
        super().__init__(config.zhipu.base_url)

    def generate_text(self, prompt: str) -> Generator[str, None, None]:
        payload = {
            "model": "glm-4-airx",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "tools": [
                {
                    "type": "retrieval",
                    "retrieval": {
                        "knowledge_id": config.zhipu.knowledge_id,
                        "prompt_template": "从文档\n\"\"\"\n{{knowledge}}\n\"\"\"\n中找问题\n\"\"\"\n{{question}}\n\"\"\"\n的答案，找到答案就仅使用文档语句回答问题，找不到答案就用自身知识回答并且告诉用户该信息不是来自文档。\n不要复述问题，直接开始回答。"
                    }
                }
            ],
            "stream": True

        }

        self.headers = {
            "Authorization": config.zhipu.token,
            "Content-Type": "application/json"
        }

        for chunk in self.send_request(payload):
            res_json = chunk.split("data:")[1]
            if "[DONE]" not in res_json:
                res = json.loads(res_json)
                yield res["choices"][0]["delta"]['content']

    def generate_text_complete_sentences(self, prompt: str) -> Generator[str, None, None]:
        return super()._generate_text_complete_sentences(prompt, 10, {'、', '，', '。', '！', '？'})
