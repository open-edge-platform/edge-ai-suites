# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# tests/test_generate_report.py — unit tests for src/generate_report.py
#
# No ROS 2 or hardware required.  All tests run from the fixture KPI files.

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_report import load_session, render_report  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "baseline"


@pytest.fixture()
def kpi1():
    return json.loads((FIXTURE_DIR / "kpi.json").read_text())


@pytest.fixture()
def kpi2():
    return json.loads((FIXTURE_DIR / "kpi_level2.json").read_text())


@pytest.fixture()
def report_l1_only(kpi1):
    return render_report(kpi1, kpi2=None)


@pytest.fixture()
def report_l1_l2(kpi1, kpi2):
    return render_report(kpi1, kpi2=kpi2)


# ──────────────────────────────────────────────────────────────────────────────
#  load_session
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadSession:
    def test_load_from_session_dir(self, tmp_path):
        kpi_data = {"schema_version": "level1_v1", "throughput_hz": 10.0,
                    "mean_latency_ms": 5.0, "max_jitter_ms": 1.0,
                    "min_jitter_ms": 0.1, "mean_jitter_ms": 0.5,
                    "jitter_stdev_ms": 0.2, "cpu_mean_pct": None,
                    "cpu_max_pct": None, "thermal": {}, "per_node": {},
                    "pairs": [], "metadata": {}}
        (tmp_path / "kpi.json").write_text(json.dumps(kpi_data))
        k1, k2, sd = load_session(session_dir=str(tmp_path))
        assert k1["throughput_hz"] == 10.0
        assert k2 is None
        assert sd == tmp_path

    def test_load_kpi2_when_present(self, tmp_path):
        base = json.loads((FIXTURE_DIR / "kpi.json").read_text())
        l2 = json.loads((FIXTURE_DIR / "kpi_level2.json").read_text())
        (tmp_path / "kpi.json").write_text(json.dumps(base))
        (tmp_path / "kpi_level2.json").write_text(json.dumps(l2))
        _, k2, _ = load_session(session_dir=str(tmp_path))
        assert k2 is not None
        assert k2["schema_version"] == "level2_v1"

    def test_load_from_explicit_paths(self):
        k1, k2, sd = load_session(
            session_dir=None,
            kpi_path=str(FIXTURE_DIR / "kpi.json"),
            kpi2_path=str(FIXTURE_DIR / "kpi_level2.json"),
        )
        assert k1["schema_version"] == "level1_v1"
        assert k2["schema_version"] == "level2_v1"
        assert sd is None


# ──────────────────────────────────────────────────────────────────────────────
#  render_report — structural correctness
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderReport:
    def test_output_is_valid_html_doctype(self, report_l1_only):
        assert report_l1_only.strip().startswith("<!DOCTYPE html>")

    def test_contains_html_and_body_tags(self, report_l1_only):
        assert "<html" in report_l1_only
        assert "</html>" in report_l1_only
        assert "<body" in report_l1_only
        assert "</body>" in report_l1_only

    def test_contains_level1_section_marker(self, report_l1_only):
        assert "Level 1 KPI" in report_l1_only

    def test_contains_thermal_section_marker(self, report_l1_only):
        assert "Thermal" in report_l1_only

    def test_no_level2_section_when_absent(self, report_l1_only):
        assert "Level 2 KPI" not in report_l1_only

    def test_contains_level2_section_when_present(self, report_l1_l2):
        assert "Level 2 KPI" in report_l1_l2

    def test_bottleneck_stage_highlighted(self, report_l1_l2, kpi2):
        bottleneck = kpi2["bottleneck_stage"]
        assert "stage-box bottleneck" in report_l1_l2
        assert bottleneck in report_l1_l2

    def test_pipeline_stages_present(self, report_l1_l2, kpi2):
        for stage in kpi2["pipeline"]["stage_sequence"]:
            assert stage in report_l1_l2

    def test_per_node_names_present(self, report_l1_only, kpi1):
        for node in kpi1["per_node"]:
            assert node in report_l1_only

    def test_throughput_value_present(self, report_l1_only, kpi1):
        assert str(kpi1["throughput_hz"]) in report_l1_only

    def test_no_cdn_or_external_urls(self, report_l1_l2):
        forbidden = ["cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com",
                     "fonts.googleapis.com", "ajax.googleapis.com"]
        for url in forbidden:
            assert url not in report_l1_l2

    def test_no_http_links_at_all(self, report_l1_l2):
        # src= and href= should not contain http:// (would require network)
        import re
        external = re.findall(r'(?:src|href)=["\']https?://', report_l1_l2)
        assert not external, f"Found external URL references: {external}"

    def test_null_thermal_renders_na(self, kpi1):
        kpi1["thermal"] = {
            "cpu_temp_c": None, "gpu_temp_c": None, "npu_temp_c": None,
            "cpu_throttled": None, "gpu_throttled": None, "npu_throttled": None,
        }
        html = render_report(kpi1)
        assert "N/A" in html

    def test_null_cpu_pct_renders_na(self, kpi1):
        kpi1["cpu_mean_pct"] = None
        kpi1["cpu_max_pct"] = None
        html = render_report(kpi1)
        assert "N/A" in html


# ──────────────────────────────────────────────────────────────────────────────
#  render_report — file output
# ──────────────────────────────────────────────────────────────────────────────

class TestFileOutput:
    def test_writes_html_file(self, tmp_path, kpi1):
        out = tmp_path / "report.html"
        html = render_report(kpi1)
        out.write_text(html, encoding="utf-8")
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_report_utf8_encoded(self, tmp_path, kpi1):
        out = tmp_path / "report.html"
        html = render_report(kpi1)
        out.write_text(html, encoding="utf-8")
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
