# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Paraformer transcription: the return contract, then the words themselves.

Marked ``slow``: this loads the real FunASR model and downloads a sample clip.
Run the rest of the suite with ``-m "not slow"``.
"""

import os
import re
import tempfile
import unittest

import pytest
import requests

from components.asr.funasr.paraformer import FUNASR_MODEL_MAP, Paraformer
from utils.config_loader import config

pytestmark = pytest.mark.slow

_SAMPLES = {
    "zh": ("https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav",
           "欢迎大家来体验达摩院推出的语音识别模型。"),
    "en": ("https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_en.wav",
           "he tried to think how it could be."),
}

# The weights on disk are the ones config.yaml names: get_asr_model_path()
# builds its directory from `models.asr.name`, not from the argument Paraformer
# is given. Testing any other entry of FUNASR_MODEL_MAP would download those
# weights into the configured model's directory, so the test follows the config.
CONFIGURED_MODEL = str(config.models.asr.name)
_LANGUAGE = "zh" if CONFIGURED_MODEL.endswith("-zh") else \
            "en" if CONFIGURED_MODEL.endswith("-en") else None

_PUNCT = re.compile(r"[\s，。、；：,.;:!?！？\-—_'\"“”‘’()（）]+")


def _normalized(text):
    """ASR punctuation comes from a separate model; the words are the contract."""
    return _PUNCT.sub("", text).lower()


def _fetch(url, path):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(path, "wb") as f:
        f.write(response.content)


class TestParaformer(unittest.TestCase):
    """One model load for the whole class; loading it is the expensive part."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="paraformer-test-")
        cls.paraformer = Paraformer(CONFIGURED_MODEL, device="cpu")

    @classmethod
    def tearDownClass(cls):
        for name in os.listdir(cls.tmp):
            os.remove(os.path.join(cls.tmp, name))
        os.rmdir(cls.tmp)

    def _sample(self, language):
        url, expected = _SAMPLES[language]
        path = os.path.join(self.tmp, f"asr_example_{language}.wav")
        if not os.path.exists(path):
            _fetch(url, path)
        return path, expected

    # ------------------------------------------------------------ construction

    def test_the_configured_model_loads(self):
        self.assertIn(CONFIGURED_MODEL, FUNASR_MODEL_MAP)
        self.assertIsNotNone(self.paraformer.model)

    def test_an_unknown_model_name_is_rejected(self):
        with self.assertRaises(ValueError):
            Paraformer("invalid-model", device="cpu")

    # -------------------------------------------------------- the return shape

    def test_transcribe_returns_text_and_timed_segments(self):
        """The shape callers rely on. It used to be a bare string."""
        path, _ = self._sample(_LANGUAGE or "zh")
        result = self.paraformer.transcribe(path)

        self.assertIsInstance(result, dict)
        self.assertEqual({"text", "segments"}, set(result))
        self.assertIsInstance(result["text"], str)
        self.assertTrue(result["text"].strip(), "the sample clip is not silent")

        self.assertIsInstance(result["segments"], list)
        self.assertTrue(result["segments"], "sentence_timestamp=True must yield segments")
        for segment in result["segments"]:
            self.assertEqual({"start", "end", "text"}, set(segment))
            self.assertGreaterEqual(segment["start"], 0.0)
            self.assertGreater(segment["end"], segment["start"])

        # Seconds, not the milliseconds FunASR reports: a 5-second clip cannot
        # end in the thousands.
        self.assertLess(result["segments"][-1]["end"], 600.0)

        # In order, and the segments spell out the same words as `text`.
        starts = [s["start"] for s in result["segments"]]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(
            _normalized("".join(s["text"] for s in result["segments"])),
            _normalized(result["text"]),
        )

    def test_a_missing_file_yields_the_empty_shape(self):
        """Callers get the same keys on failure, so none of them special-case it."""
        result = self.paraformer.transcribe(os.path.join(self.tmp, "not-here.wav"))
        self.assertEqual({"text": "", "segments": []}, result)

    # ------------------------------------------------------------- the content

    @unittest.skipIf(_LANGUAGE is None,
                     f"{CONFIGURED_MODEL} is not a single-language model")
    def test_transcribe_matches_the_reference_transcript(self):
        path, expected = self._sample(_LANGUAGE)
        result = self.paraformer.transcribe(path)
        self.assertEqual(_normalized(expected), _normalized(result["text"]))

    @unittest.skipIf(_LANGUAGE != "zh", "only meaningful on the Chinese model")
    def test_english_audio_on_the_chinese_model_is_not_asserted(self):
        """Kept as a note, not a claim.

        The old test ran the English clip through whichever model came first in
        FUNASR_MODEL_MAP -- `paraformer-zh` -- and asserted an exact match
        against the English reference. Transcribing the wrong language is not a
        contract, so this only checks the call survives it.
        """
        path, _ = self._sample("en")
        result = self.paraformer.transcribe(path)
        self.assertIsInstance(result, dict)
        self.assertEqual({"text", "segments"}, set(result))


if __name__ == "__main__":
    unittest.main()
