from da.llm.zhipu_client import ZhipuRemoteClient


def test():
    client = ZhipuRemoteClient()
    for _ in client.generate_text_complete_sentences("请介绍一下这个基于英特尔视频AI计算盒的智慧汽车4S门店解决方案"):
        pass


if __name__ == '__main__':
    test()
