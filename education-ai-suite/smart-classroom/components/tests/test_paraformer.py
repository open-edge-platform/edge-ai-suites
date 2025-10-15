import unittest
import os
import requests
from components.asr.funasr.paraformer import Paraformer, FUNASR_MODEL_MAP

EN_AUDIO_EXAMPLE_URL = "https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_en.wav"
EN_AUDIO_TRANSCRIPT = "he tried to think how it could be."
ZH_AUDIO_EXAMPLE_URL = "https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav"
ZH_AUDIO_TRANSCRIPT = "欢迎大家来体验达摩院推出的语音识别模型。"

TEST_MODEL = list(FUNASR_MODEL_MAP.keys())[0]

class TestParaformer(unittest.TestCase):
    def test_initialization(self):
        # Should initialize with valid model name
        paraformer = Paraformer(TEST_MODEL, device="cpu")
        self.assertIsNotNone(paraformer.model)
        # Should raise ValueError for invalid model name
        with self.assertRaises(ValueError):
            Paraformer("invalid-model", device="cpu")

    def test_transcribe_en(self):
        local_audio_path = "asr_example_en.wav"
        response = requests.get(EN_AUDIO_EXAMPLE_URL)
        response.raise_for_status()
        with open(local_audio_path, "wb") as audio_file:
            audio_file.write(response.content)
        try:
            paraformer = Paraformer(TEST_MODEL, device="cpu")
            result = paraformer.transcribe(local_audio_path)
            if result is not None:
                result = result.strip()
            expected_transcription = EN_AUDIO_TRANSCRIPT
            print("Model generated transcript: ", result)
            print("Expected transcript: ", expected_transcription)
            self.assertEqual(expected_transcription.lower(), result.lower())
        finally:
            if os.path.exists(local_audio_path):
                os.remove(local_audio_path)

    def test_transcribe_zh(self):
        local_audio_path = "asr_example_zh.wav"
        response = requests.get(ZH_AUDIO_EXAMPLE_URL)
        response.raise_for_status()
        with open(local_audio_path, "wb") as audio_file:
            audio_file.write(response.content)
        try:
            paraformer = Paraformer(TEST_MODEL, device="cpu")
            result = paraformer.transcribe(local_audio_path)
            if result is not None:
                result = result.strip()
            expected_transcription = ZH_AUDIO_TRANSCRIPT
            print("Model generated transcript: ", result)
            print("Expected transcript: ", expected_transcription)
            self.assertEqual(expected_transcription.lower(), result.lower())
        finally:
            if os.path.exists(local_audio_path):
                os.remove(local_audio_path)

if __name__ == "__main__":
    unittest.main()