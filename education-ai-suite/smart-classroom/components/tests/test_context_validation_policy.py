# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import unittest

from components.llm.context_validation.validate_long_context import (
    _classify_failure,
    _passed,
)


def _successful_result(generate_time_s):
    return {
        "load_ok": True,
        "generate_ok": True,
        "generated_tokens": 10,
        "generate_time_s": generate_time_s,
        "max_generate_time_sec": 120,
        "gpu_memory_at_limit": False,
        "error": None,
    }


class TestContextValidationPolicy(unittest.TestCase):
    def test_48k_observed_trial_meets_latency_sla(self):
        result = _successful_result(50.7)
        result["generated_tokens"] = 64

        self.assertTrue(_passed(result))

    def test_slow_trial_without_gpu_pressure_still_passes(self):
        result = _successful_result(254.4)

        self.assertTrue(_passed(result))

    def test_slow_trial_at_gpu_memory_limit_is_too_slow(self):
        result = _successful_result(254.4)
        result["gpu_memory_at_limit"] = True

        self.assertFalse(_passed(result))
        self.assertEqual(_classify_failure(result), "too_slow")

    def test_latency_sla_is_inclusive(self):
        self.assertTrue(_passed(_successful_result(120.0)))


if __name__ == "__main__":
    unittest.main()