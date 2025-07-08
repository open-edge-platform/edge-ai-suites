from pathlib import Path

from playsound import playsound

from da.speak.tts_client import TTSClient


def test():
    tts_client = TTSClient(male=True)
    audio_path = tts_client.tts(
        "一二三四五，上山打老虎。小智同学，你好哇，最近还好吗？Hello, how are you? 老虎不在家，抓住小松鼠。",
    )
    playsound(str(Path(audio_path).absolute()))

    tts_client = TTSClient(male=False)
    audio_path = tts_client.tts(
        "一二三四五，上山打老虎。小智同学，你好哇，最近还好吗？Hello, how are you? 老虎不在家，抓住小松鼠。",
    )
    playsound(str(Path(audio_path).absolute()))


if __name__ == '__main__':
    test()
