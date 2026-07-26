# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import unittest

from components.llm.context_validation.trial_runner import _validate_generated_output


class FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        if text == "<eos>":
            return [0]
        return text.split()

    def decode(self, token_ids, skip_special_tokens=True):
        if token_ids == [0]:
            return "" if skip_special_tokens else "<eos>"
        return " ".join(token_ids)


class TestGeneratedOutputValidation(unittest.TestCase):
    def setUp(self):
        self.tokenizer = FakeTokenizer()

    def test_accepts_meaningful_output(self):
        valid, count, error = _validate_generated_output(
            "Energy changes between kinetic and potential forms.", self.tokenizer
        )
        self.assertTrue(valid)
        self.assertGreater(count, 0)
        self.assertIsNone(error)

    def test_rejects_punctuation_and_special_tokens(self):
        for output in ("!!!!", "<eos>"):
            valid, _count, error = _validate_generated_output(output, self.tokenizer)
            self.assertFalse(valid)
            self.assertIsNotNone(error)

    def test_rejects_repeated_single_character(self):
        valid, _count, error = _validate_generated_output("aaaaaaaa", self.tokenizer)
        self.assertFalse(valid)
        self.assertEqual(error, "repetitive_output")


if __name__ == "__main__":
    unittest.main()