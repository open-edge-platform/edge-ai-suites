# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import unittest

from components.llm.context_validation.haystack_builder import build_probe


class FakeTokenizer:
    """Whitespace tokenizer stand-in so this test doesn't need the real (heavy)
    transformers dependency just to exercise the budget/truncation logic."""

    def encode(self, text):
        return text.split()

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(ids)


class TestBuildProbe(unittest.TestCase):
    def test_token_budget_respected(self):
        tokenizer = FakeTokenizer()
        target_tokens = 4000
        probe = build_probe(tokenizer, target_tokens, depth=0.5, seed=1)

        self.assertLessEqual(probe.tokens_actual, target_tokens)
        self.assertGreaterEqual(probe.tokens_actual, target_tokens * 0.85)

    def test_needle_present_at_extreme_depths(self):
        tokenizer = FakeTokenizer()
        for depth in (0.0, 0.5, 1.0):
            probe = build_probe(tokenizer, 2000, depth=depth, seed=2)
            user_content = probe.messages[1]["content"]
            self.assertIn(probe.expected_code, user_content, f"needle missing at depth={depth}")

    def test_needle_depth_ordering(self):
        tokenizer = FakeTokenizer()
        early = build_probe(tokenizer, 4000, depth=0.1, seed=3)
        late = build_probe(tokenizer, 4000, depth=0.9, seed=3)

        early_content = early.messages[1]["content"]
        late_content = late.messages[1]["content"]
        early_pos = early_content.index(early.expected_code) / len(early_content)
        late_pos = late_content.index(late.expected_code) / len(late_content)

        self.assertLess(early_pos, 0.3)
        self.assertGreater(late_pos, 0.7)
        self.assertLess(early_pos, late_pos)

    def test_deterministic_for_fixed_seed(self):
        tokenizer = FakeTokenizer()
        probe_a = build_probe(tokenizer, 3000, depth=0.4, seed=42)
        probe_b = build_probe(tokenizer, 3000, depth=0.4, seed=42)

        self.assertEqual(probe_a.expected_code, probe_b.expected_code)
        self.assertEqual(probe_a.messages, probe_b.messages)

    def test_invalid_depth_raises(self):
        tokenizer = FakeTokenizer()
        with self.assertRaises(ValueError):
            build_probe(tokenizer, 1000, depth=1.5, seed=0)


if __name__ == "__main__":
    unittest.main()
