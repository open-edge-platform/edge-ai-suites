# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import unittest

from components.llm.context_validation.validate_long_context import (
    _theoretical_kv_bytes_per_token,
)


class TestTheoreticalKvBytesPerToken(unittest.TestCase):
    def test_dense_model_without_layer_types_counts_every_layer(self):
        # Ordinary transformer (e.g. Qwen3-8B): every layer is a standard
        # growing-KV-cache attention layer.
        config = {
            "num_hidden_layers": 36,
            "num_key_value_heads": 8,
            "head_dim": 128,
        }
        expected = 2 * 36 * 8 * 128 * 2
        self.assertEqual(_theoretical_kv_bytes_per_token(config), expected)

    def test_hybrid_model_counts_only_full_attention_layers(self):
        # Mirrors the real Qwen3.5-9B config.json shape: 32 layers, repeating
        # 3x linear_attention + 1x full_attention (8 full_attention layers
        # total). Only those 8 should count toward growing KV-cache memory --
        # the linear_attention/Mamba-style layers hold an O(1) recurrent
        # state, not one that grows with token count.
        layer_types = (["linear_attention"] * 3 + ["full_attention"]) * 8
        config = {
            "text_config": {
                "num_hidden_layers": 32,
                "num_key_value_heads": 4,
                "head_dim": 256,
                "layer_types": layer_types,
            }
        }
        full_attention_layers = 8
        expected = 2 * full_attention_layers * 4 * 256 * 2
        self.assertEqual(_theoretical_kv_bytes_per_token(config), expected)

    def test_vlm_config_reads_nested_text_config(self):
        # VLM exports nest the causal-LM attention params under text_config
        # instead of at the top level.
        config = {
            "architectures": ["SomeForConditionalGeneration"],
            "vision_config": {"hidden_size": 1152},
            "text_config": {
                "num_hidden_layers": 28,
                "num_key_value_heads": 4,
                "head_dim": 128,
            },
        }
        expected = 2 * 28 * 4 * 128 * 2
        self.assertEqual(_theoretical_kv_bytes_per_token(config), expected)

    def test_missing_required_keys_returns_none(self):
        config = {"text_config": {"num_hidden_layers": 32, "head_dim": 128}}
        self.assertIsNone(_theoretical_kv_bytes_per_token(config))

    def test_layer_types_with_no_full_attention_returns_none(self):
        config = {
            "num_hidden_layers": 4,
            "num_key_value_heads": 4,
            "head_dim": 128,
            "layer_types": ["linear_attention"] * 4,
        }
        self.assertIsNone(_theoretical_kv_bytes_per_token(config))

    def test_custom_kv_cache_dtype_bytes(self):
        config = {
            "num_hidden_layers": 10,
            "num_key_value_heads": 2,
            "head_dim": 64,
        }
        # int8 KV cache (1 byte/element) instead of the fp16 default.
        expected = 2 * 10 * 2 * 64 * 1
        self.assertEqual(
            _theoretical_kv_bytes_per_token(config, kv_cache_dtype_bytes=1), expected
        )


if __name__ == "__main__":
    unittest.main()
