import uuid
from pathlib import Path

from paddlespeech.cli.tts import TTSExecutor

from da.util.log import logger


class TTSClient:
    def __init__(self, male: bool = False):
        self.male = male
        self.tts_executor = TTSExecutor()
        self.warmup()
        logger.info("TTSClient initialized")

    def warmup(self):
        self.tts("模型初始化")

    def tts(self, text: str) -> str:
        Path("output/tmp").mkdir(exist_ok=True, parents=True)
        tmp_file_path = f"output/tmp/{uuid.uuid4()}.wav"

        if self.male:
            audio_path = self._tts_male(text, tmp_file_path)
        else:
            audio_path = self._tts_female(text, tmp_file_path)

        logger.info(f"TTS {text} saved to {audio_path}")
        return audio_path

    def _tts_male(self, text: str, tmp_file_path: str):
        wav = self.tts_executor(
            text=text,
            am="fastspeech2_male",
            spk_id=167,
            voc="pwgan_male",
            lang="mix",
            device="cpu",
            use_onnx=True,
            cpu_threads=4,
            output=tmp_file_path
        )

        return wav

    def _tts_female(self, text: str, tmp_file_path: str):
        wav = self.tts_executor(
            text=text,
            am="fastspeech2_mix",
            spk_id=174,
            voc="pwgan_csmsc",
            lang="mix",
            device="cpu",
            use_onnx=True,
            cpu_threads=4,
            output=tmp_file_path
        )

        return wav
