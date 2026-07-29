# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_visualize_kpi.py — unit tests for src/visualize_kpi.py

No ROS 2 or hardware required.  All tests run headlessly via the Agg
matplotlib backend set at import time in the module under test.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from visualize_kpi import (  # noqa: E402
    extract_node_stats,
    latency_histogram,
    load_kpi,
    resource_utilization,
    sku_comparison,
    throughput_drop,
    _infer_sku_label,
    _representative_pair,
)

# ──────────────────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "baseline"


@pytest.fixture()
def kpi1():
    return json.loads((FIXTURE_DIR / "kpi.json").read_text())


@pytest.fixture()
def minimal_kpi():
    """KPI with a single node and no pairs — tests graceful fallback."""
    return {
        "schema_version": "level1_v1",
        "per_node": {
            "/solo_node": {
                "throughput_hz": 10.0,
                "mean_latency_ms": 25.0,
                "mean_jitter_ms": 2.0,
                "max_jitter_ms": 6.0,
                "num_samples": 50,
                "primary_input": "/in",
                "primary_output": "/out",
                "pipeline_stage": "Control",
            }
        },
        "pairs": [],
        "metadata": {"name": "test_session"},
    }


@pytest.fixture()
def empty_kpi():
    """KPI with no per_node data."""
    return {"schema_version": "level1_v1", "per_node": {}, "pairs": []}


# ──────────────────────────────────────────────────────────────────────────────
#  _infer_sku_label
# ──────────────────────────────────────────────────────────────────────────────

class TestInferSkuLabel:
    def _make_kpi(self, cpu_model=None, hostname="testhost"):
        return {
            "metadata": {
                "hostname": hostname,
                "hardware": {"cpu_model": cpu_model},
            }
        }

    def test_raptor_lake_13th_gen(self):
        kpi = self._make_kpi("13th Gen Intel(R) Core(TM) i7-1370P")
        assert _infer_sku_label(kpi) == "RPL"

    def test_raptor_lake_refresh_14th_gen(self):
        kpi = self._make_kpi("14th Gen Intel(R) Core(TM) i9-14900K")
        assert _infer_sku_label(kpi) == "RPL-R"

    def test_meteor_lake(self):
        kpi = self._make_kpi("Intel(R) Core(TM) Ultra 7 165U")
        assert _infer_sku_label(kpi) == "MTL"

    def test_arrow_lake(self):
        kpi = self._make_kpi("Intel(R) Core(TM) Ultra 9 285K")
        assert _infer_sku_label(kpi) == "ARL"

    def test_panther_lake(self):
        kpi = self._make_kpi("Intel(R) Core(TM) Ultra 7 365H")
        assert _infer_sku_label(kpi) == "PTL"

    def test_alder_lake_n_n100(self):
        kpi = self._make_kpi("Intel(R) Processor N100")
        assert _infer_sku_label(kpi) == "ADL-N"

    def test_alder_lake_n_i3_n305(self):
        kpi = self._make_kpi("Intel(R) Core(TM) i3-N305")
        assert _infer_sku_label(kpi) == "ADL-N"

    def test_falls_back_to_model_number_when_no_pattern(self):
        kpi = self._make_kpi("Intel(R) Pentium(R) Gold G6405")
        label = _infer_sku_label(kpi)
        # Should not be empty and should not raise
        assert label

    def test_falls_back_to_hostname_when_no_cpu_model(self):
        kpi = self._make_kpi(cpu_model=None, hostname="myrobot")
        assert _infer_sku_label(kpi) == "myrobot"

    def test_returns_unknown_when_no_metadata(self):
        assert _infer_sku_label({}) == "unknown"


# ──────────────────────────────────────────────────────────────────────────────
#  _representative_pair
# ──────────────────────────────────────────────────────────────────────────────

class TestRepresentativePair:
    def test_returns_highest_n(self):
        pairs = [
            {"node": "/a", "n": 10, "mean_ms": 5.0},
            {"node": "/a", "n": 50, "mean_ms": 7.0},
            {"node": "/a", "n": 20, "mean_ms": 6.0},
        ]
        result = _representative_pair("/a", pairs)
        assert result["n"] == 50

    def test_returns_empty_when_no_match(self):
        pairs = [{"node": "/other", "n": 100}]
        assert _representative_pair("/missing", pairs) == {}

    def test_returns_empty_for_empty_pairs(self):
        assert _representative_pair("/node", []) == {}


# ──────────────────────────────────────────────────────────────────────────────
#  extract_node_stats
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractNodeStats:
    def test_returns_one_row_per_node(self, kpi1):
        rows = extract_node_stats(kpi1)
        assert len(rows) == len(kpi1["per_node"])

    def test_sorted_by_mean_descending(self, kpi1):
        rows = extract_node_stats(kpi1)
        means = [r["mean_ms"] for r in rows if r["mean_ms"] is not None]
        assert means == sorted(means, reverse=True)

    def test_short_name_strips_leading_slash(self, kpi1):
        rows = extract_node_stats(kpi1)
        for row in rows:
            assert not row["short"].startswith("/")

    def test_stage_defaults_to_other(self):
        kpi = {
            "per_node": {
                "/x": {"mean_latency_ms": 10.0, "throughput_hz": 1.0}
            },
            "pairs": [],
        }
        rows = extract_node_stats(kpi)
        assert rows[0]["stage"] == "Other"

    def test_p50_p90_from_representative_pair(self, kpi1):
        rows = extract_node_stats(kpi1)
        # fixture has pairs with p50_ms / p90_ms
        for row in rows:
            assert row["p50_ms"] is not None or row["p90_ms"] is None

    def test_empty_per_node_returns_empty_list(self, empty_kpi):
        assert not extract_node_stats(empty_kpi)

    def test_no_pairs_yields_none_p50_p90(self, minimal_kpi):
        rows = extract_node_stats(minimal_kpi)
        assert len(rows) == 1
        assert rows[0]["p50_ms"] is None
        assert rows[0]["p90_ms"] is None


# ──────────────────────────────────────────────────────────────────────────────
#  load_kpi
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadKpi:
    def test_loads_fixture(self):
        kpi = load_kpi(FIXTURE_DIR / "kpi.json")
        assert "per_node" in kpi
        assert "schema_version" in kpi

    def test_missing_file_raises_system_exit(self, tmp_path):
        with pytest.raises(SystemExit):
            load_kpi(tmp_path / "nonexistent.json")

    def test_invalid_json_raises_system_exit(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json }")
        with pytest.raises(SystemExit):
            load_kpi(bad)


# ──────────────────────────────────────────────────────────────────────────────
#  latency_histogram
# ──────────────────────────────────────────────────────────────────────────────

class TestLatencyHistogram:
    def test_creates_png_file(self, kpi1, tmp_path):
        result = latency_histogram(kpi1, tmp_path, fmt="png")
        assert result is not None
        assert result.exists()
        assert result.suffix == ".png"
        assert result.name == "latency_histogram.png"

    def test_creates_svg_file(self, kpi1, tmp_path):
        result = latency_histogram(kpi1, tmp_path, fmt="svg")
        assert result is not None
        assert result.suffix == ".svg"

    def test_returns_none_for_empty_kpi(self, empty_kpi, tmp_path):
        result = latency_histogram(empty_kpi, tmp_path)
        assert result is None

    def test_works_with_minimal_single_node(self, minimal_kpi, tmp_path):
        result = latency_histogram(minimal_kpi, tmp_path)
        assert result is not None
        assert result.exists()

    def test_output_dir_is_created(self, kpi1, tmp_path):
        nested = tmp_path / "a" / "b" / "charts"
        latency_histogram(kpi1, nested)
        assert nested.exists()

    def test_uses_session_name_in_title(self, kpi1, tmp_path):
        # Just verify it runs without error when metadata.name is present
        result = latency_histogram(kpi1, tmp_path)
        assert result is not None


# ──────────────────────────────────────────────────────────────────────────────
#  sku_comparison
# ──────────────────────────────────────────────────────────────────────────────

class TestSkuComparison:
    def test_returns_none_for_single_kpi(self, kpi1, tmp_path):
        result = sku_comparison([kpi1], ["MTL"], tmp_path)
        assert result is None

    def test_creates_png_for_two_kpis(self, kpi1, tmp_path):
        result = sku_comparison([kpi1, kpi1], ["MTL", "ARL"], tmp_path)
        assert result is not None
        assert result.exists()
        assert result.name == "sku_comparison.png"

    def test_creates_svg_format(self, kpi1, tmp_path):
        result = sku_comparison([kpi1, kpi1], ["MTL", "ARL"], tmp_path, fmt="svg")
        assert result is not None
        assert result.suffix == ".svg"

    def test_handles_three_skus(self, kpi1, tmp_path):
        result = sku_comparison([kpi1, kpi1, kpi1], ["MTL", "ARL", "PTL"], tmp_path)
        assert result is not None
        assert result.exists()

    def test_handles_node_missing_from_one_sku(self, kpi1, minimal_kpi, tmp_path):
        # kpi1 has 3 nodes; minimal_kpi has 1 — should not raise.
        result = sku_comparison([kpi1, minimal_kpi], ["Full", "Mini"], tmp_path)
        assert result is not None
        assert result.exists()

    def test_output_dir_is_created(self, kpi1, tmp_path):
        nested = tmp_path / "deep" / "charts"
        sku_comparison([kpi1, kpi1], ["A", "B"], nested)
        assert nested.exists()


# ──────────────────────────────────────────────────────────────────────────────
#  resource_utilization
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def resource_kpi():
    """KPI with fully populated CPU and thermal resource data."""
    return {
        "schema_version": "level1_v1",
        "cpu_mean_pct": 42.5,
        "cpu_max_pct": 78.0,
        "thermal": {
            "cpu_temp_c": 65.0,
            "gpu_temp_c": 71.0,
            "npu_temp_c": 55.0,
            "cpu_throttled": False,
            "gpu_throttled": False,
            "npu_throttled": False,
        },
        "per_node": {},
        "pairs": [],
        "metadata": {"name": "hw_session"},
    }


@pytest.fixture()
def throttled_kpi():
    """KPI where CPU is throttled."""
    return {
        "schema_version": "level1_v1",
        "cpu_mean_pct": 95.0,
        "cpu_max_pct": 100.0,
        "thermal": {
            "cpu_temp_c": 99.0,
            "gpu_temp_c": None,
            "npu_temp_c": None,
            "cpu_throttled": True,
            "gpu_throttled": False,
            "npu_throttled": False,
        },
        "per_node": {},
        "pairs": [],
        "metadata": {"name": "throttle_session"},
    }


class TestResourceUtilization:
    def test_returns_none_when_all_null(self, tmp_path):
        # All resource fields absent / null — common on WSL2.
        kpi = {
            "cpu_mean_pct": None,
            "cpu_max_pct": None,
            "thermal": {"cpu_temp_c": None, "gpu_temp_c": None, "npu_temp_c": None},
            "per_node": {},
            "pairs": [],
        }
        result = resource_utilization(kpi, tmp_path)
        assert result is None

    def test_creates_png_with_resource_data(self, resource_kpi, tmp_path):
        result = resource_utilization(resource_kpi, tmp_path)
        assert result is not None
        assert result.exists()
        assert result.name == "resource_utilization.png"

    def test_creates_svg_format(self, resource_kpi, tmp_path):
        result = resource_utilization(resource_kpi, tmp_path, fmt="svg")
        assert result is not None
        assert result.suffix == ".svg"

    def test_partial_data_only_cpu(self, tmp_path):
        kpi = {
            "cpu_mean_pct": 30.0,
            "cpu_max_pct": None,
            "thermal": {"cpu_temp_c": None, "gpu_temp_c": None, "npu_temp_c": None},
            "per_node": {},
            "pairs": [],
            "metadata": {"name": "partial"},
        }
        result = resource_utilization(kpi, tmp_path)
        assert result is not None
        assert result.exists()

    def test_throttled_kpi_renders(self, throttled_kpi, tmp_path):
        result = resource_utilization(throttled_kpi, tmp_path)
        assert result is not None
        assert result.exists()

    def test_output_dir_is_created(self, resource_kpi, tmp_path):
        nested = tmp_path / "res" / "charts"
        resource_utilization(resource_kpi, nested)
        assert nested.exists()


# ──────────────────────────────────────────────────────────────────────────────
#  throughput_drop
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def kpi2_single_stage():
    """Minimal kpi_level2.json with a single Perception stage."""
    return {
        "schema_version": "level2_v1",
        "pipeline": {
            "input_topic": "/camera/image",
            "output_topic": "/world/map",
            "stage_sequence": ["Perception"],
        },
        "e2e_latency_ms": {
            "mean": 63.7, "p50": 63.7, "p90": 67.3, "p99": None, "max": 68.2,
            "n": 144, "method": "chained",
        },
        "throughput_hz": None,
        "drop_rate_pct": None,
        "bottleneck_stage": "Perception",
        "stage_latency_ms": {
            "Perception": {
                "mean_ms": 63.7, "p50_ms": 63.7, "p90_ms": 67.3,
                "p99_ms": None, "max_ms": 68.2, "n": 144,
            },
        },
        "metadata": {"name": "test_l2"},
    }


@pytest.fixture()
def kpi2_multi_stage():
    """kpi_level2.json with throughput, drop rate, and multiple stages."""
    return {
        "schema_version": "level2_v1",
        "pipeline": {
            "input_topic": "/scan",
            "output_topic": "/cmd_vel",
            "stage_sequence": ["Perception", "Planning", "Control"],
        },
        "e2e_latency_ms": {
            "mean": 120.0, "p50": 115.0, "p90": 180.0, "p99": 220.0, "max": 250.0,
            "n": 500, "method": "chained",
        },
        "throughput_hz": 19.5,
        "drop_rate_pct": 2.1,
        "bottleneck_stage": "Perception",
        "stage_latency_ms": {
            "Perception": {"mean_ms": 80.0, "p50_ms": 78.0, "p90_ms": 110.0,
                           "p99_ms": 140.0, "max_ms": 160.0, "n": 500},
            "Planning":   {"mean_ms": 25.0, "p50_ms": 24.0, "p90_ms":  40.0,
                           "p99_ms":  55.0, "max_ms":  70.0, "n": 500},
            "Control":    {"mean_ms": 15.0, "p50_ms": 14.5, "p90_ms":  22.0,
                           "p99_ms":  30.0, "max_ms":  35.0, "n": 500},
        },
        "metadata": {"name": "multi_stage"},
    }


class TestThroughputDrop:
    def test_returns_none_for_none_input(self, tmp_path):
        assert throughput_drop(None, tmp_path) is None

    def test_returns_none_when_no_e2e_data(self, tmp_path):
        kpi2 = {"e2e_latency_ms": {"mean": None}, "metadata": {}}
        assert throughput_drop(kpi2, tmp_path) is None

    def test_creates_png_single_stage(self, kpi2_single_stage, tmp_path):
        result = throughput_drop(kpi2_single_stage, tmp_path)
        assert result is not None
        assert result.exists()
        assert result.name == "throughput_drop.png"

    def test_creates_svg_format(self, kpi2_single_stage, tmp_path):
        result = throughput_drop(kpi2_single_stage, tmp_path, fmt="svg")
        assert result is not None
        assert result.suffix == ".svg"

    def test_creates_png_multi_stage(self, kpi2_multi_stage, tmp_path):
        result = throughput_drop(kpi2_multi_stage, tmp_path)
        assert result is not None
        assert result.exists()

    def test_output_dir_is_created(self, kpi2_single_stage, tmp_path):
        nested = tmp_path / "l2" / "charts"
        throughput_drop(kpi2_single_stage, nested)
        assert nested.exists()
