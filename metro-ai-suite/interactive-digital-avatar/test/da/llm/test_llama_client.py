from da.llm.llama_client import LlamaRemoteClient


def test():
    client = LlamaRemoteClient()
    for _ in client.generate_text_complete_sentences("你好，请介绍一下你自己。"):
        pass


if __name__ == '__main__':
    test()
