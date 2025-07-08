from da.llm.qwen_client import QwenRemoteClient, QwenLocalClient


def test_remote():
    client = QwenRemoteClient()
    for _ in client.generate_text_complete_sentences("你好，请介绍一下你自己。"):
        pass


def test_local():
    client = QwenLocalClient()
    for _ in client.generate_text_complete_sentences("你好，请介绍一下你自己。"):
        pass


if __name__ == '__main__':
    test_remote()
    test_local()
