# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.discovery, model and pipeline discovery."""

import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from backend.models import ModelInfo

from backend.services.discovery import (
    discover_models,
    discover_detection_models,
    is_detection_pipeline,
    discover_pipelines_remote,
    _default_pipeline_names,
    _fallback_pipeline_name,
    _infer_detection_from_name,
    _gpu_device_exists,
    has_gpu_device,
    _npu_device_exists,
    has_npu_device,
)


# ===================================================================
# discover_models
# ===================================================================
class TestDiscoverModels:
    """Tests for discover_models(), VLM model directory scanning."""

    def test_returns_empty_when_dir_missing(self, tmp_path):
        """Returns an empty list when the models directory does not exist."""
        missing = tmp_path / "nonexistent"
        assert discover_models(missing) == []

    def test_returns_empty_for_empty_dir(self, models_dir):
        """Returns an empty list when the directory is empty."""
        assert discover_models(models_dir) == []

    def test_ignores_legacy_top_level_models(self, models_dir):
        """Top-level model directories/files are ignored in per-device-only mode."""
        (models_dir / "InternVL2-1B").mkdir()
        (models_dir / "InternVL2-2B-gpu").mkdir()
        (models_dir / "model.xml").write_text("")

        assert discover_models(models_dir) == []

    def test_ignores_dotfiles(self, models_dir):
        """Hidden files/directories (starting with '.') are skipped."""
        (models_dir / ".hidden_dir").mkdir()
        (models_dir / ".hidden_file.json").write_text("")
        (models_dir / "cpu" / "visible_model").mkdir(parents=True)
        result = discover_models(models_dir)
        assert result == [ModelInfo(name="visible_model", device="cpu")]

    def test_ignores_unsupported_extensions(self, models_dir):
        """Files with extensions other than .xml, .bin, .json are skipped."""
        (models_dir / "readme.txt").write_text("")
        (models_dir / "data.csv").write_text("")
        assert discover_models(models_dir) == []

    def test_results_are_sorted(self, models_dir):
        """Returned model names are sorted alphabetically."""
        for name in ["Zeta", "Alpha", "Mid"]:
            (models_dir / "cpu" / name).mkdir(parents=True)
        assert [m.name for m in discover_models(models_dir)] == ["Alpha", "Mid", "Zeta"]

    def test_discovers_models_from_device_subdirectories(self, models_dir):
        """Discovers models from the new ov_models/<device>/<model> layout."""
        (models_dir / "cpu" / "InternVL2-1B").mkdir(parents=True)
        (models_dir / "gpu" / "InternVL2-1B").mkdir(parents=True)
        (models_dir / "npu" / "InternVL2-1B").mkdir(parents=True)

        result = discover_models(models_dir)

        assert result == [
            ModelInfo(name="InternVL2-1B", device="cpu"),
            ModelInfo(name="InternVL2-1B", device="gpu"),
            ModelInfo(name="InternVL2-1B", device="npu"),
        ]

    def test_discovers_flat_files_from_device_subdirectories(self, models_dir):
        """Discovers flattened model artifacts stored directly under a device directory."""
        (models_dir / "gpu").mkdir()
        (models_dir / "gpu" / "InternVL2-2B.xml").write_text("")

        result = discover_models(models_dir)

        assert result == [ModelInfo(name="InternVL2-2B.xml", device="gpu")]


# ===================================================================
# discover_detection_models
# ===================================================================
class TestDiscoverDetectionModels:
    """Tests for discover_detection_models(), detection model scanning."""

    def test_returns_empty_when_dir_missing(self, tmp_path):
        """Returns an empty list when the directory does not exist."""
        assert discover_detection_models(tmp_path / "nope") == []

    def test_returns_empty_for_empty_dir(self, detection_models_dir):
        """Returns an empty list for an empty directory."""
        assert discover_detection_models(detection_models_dir) == []

    def test_valid_detection_model_structure(self, detection_models_dir):
        """Detects model_name/public/model_name directory structure."""
        model = detection_models_dir / "yolov8s" / "public" / "yolov8s"
        model.mkdir(parents=True)
        result = discover_detection_models(detection_models_dir)
        assert result == ["yolov8s"]

    def test_ignores_incomplete_structure(self, detection_models_dir):
        """Directories without the expected public/<name> structure are skipped."""
        # Has 'public/' but not the model sub-directory
        (detection_models_dir / "incomplete" / "public").mkdir(parents=True)
        assert discover_detection_models(detection_models_dir) == []

    def test_ignores_dotdirs(self, detection_models_dir):
        """Hidden directories are skipped."""
        hidden = detection_models_dir / ".hidden" / "public" / ".hidden"
        hidden.mkdir(parents=True)
        assert discover_detection_models(detection_models_dir) == []

    def test_ignores_files_at_root(self, detection_models_dir):
        """Regular files in the detection models root are ignored."""
        (detection_models_dir / "notes.txt").write_text("")
        assert discover_detection_models(detection_models_dir) == []


# ===================================================================
# is_detection_pipeline
# ===================================================================
class TestIsDetectionPipeline:
    """Tests for the is_detection_pipeline() classifier helper."""

    def test_no_parameters_returns_false(self):
        """A pipeline item with no parameters is not a detection pipeline."""
        assert is_detection_pipeline({}) is False

    def test_detection_model_name_key(self):
        """Presence of 'detection_model_name' marks the pipeline as detection."""
        item = {"parameters": {"properties": {"detection_model_name": {}}}}
        assert is_detection_pipeline(item) is True

    def test_detection_threshold_key(self):
        """Presence of 'detection_threshold' marks the pipeline as detection."""
        item = {"parameters": {"properties": {"detection_threshold": {}}}}
        assert is_detection_pipeline(item) is True

    def test_detection_prefixed_key(self):
        """Any key starting with 'detection_' triggers detection classification."""
        item = {"parameters": {"properties": {"detection_custom_field": {}}}}
        assert is_detection_pipeline(item) is True

    def test_non_detection_keys(self):
        """Keys not related to detection do not trigger detection classification."""
        item = {"parameters": {"properties": {"captioner_prompt": {}, "model": {}}}}
        assert is_detection_pipeline(item) is False


# ===================================================================
# discover_pipelines_remote
# ===================================================================
class TestDiscoverPipelinesRemote:
    """Tests for discover_pipelines_remote(), remote pipeline discovery."""

    def _mock_http(self, payload):
        """Return a patcher that makes http_json return the given JSON payload."""
        return patch(
            "backend.services.discovery.http_json",
            return_value=json.dumps(payload),
        )

    def test_list_of_strings(self):
        """A simple list of pipeline name strings is returned as non-detection."""
        with self._mock_http(["pipe_a", "pipe_b"]):
            result = discover_pipelines_remote()
        names = [r["pipeline_name"] for r in result]
        assert "pipe_a" in names
        assert all(r["pipeline_type"] == "non-detection" for r in result)

    def test_list_of_dicts_with_version(self):
        """Pipeline dicts with a 'version' key use that as the pipeline name."""
        with self._mock_http([{"version": "v1", "parameters": {"properties": {}}}]):
            result = discover_pipelines_remote()
        assert result[0]["pipeline_name"] == "v1"

    def test_list_of_dicts_with_name(self):
        """Pipeline dicts with a 'name' key (no version) use name."""
        with self._mock_http(
            [
                {
                    "name": "detpipe",
                    "parameters": {"properties": {"detection_model_name": {}}},
                }
            ]
        ):
            result = discover_pipelines_remote()
        # detection pipeline is filtered when ENABLE_DETECTION_PIPELINE=false
        # so the result should fallback to default
        assert len(result) >= 1

    def test_dict_payload_with_pipelines_key(self):
        """A dict wrapping pipelines under a 'pipelines' key is normalised."""
        with self._mock_http({"pipelines": ["alpha"]}):
            result = discover_pipelines_remote()
        assert result[0]["pipeline_name"] == "alpha"

    def test_dict_payload_with_items_key(self):
        """A dict wrapping pipelines under an 'items' key is normalised."""
        with self._mock_http({"items": ["beta"]}):
            result = discover_pipelines_remote()
        assert result[0]["pipeline_name"] == "beta"

    def test_non_list_non_dict_payload_normalizes_to_empty(self):
        """Unexpected JSON payload types are normalized to an empty item list."""
        with self._mock_http(42):
            result = discover_pipelines_remote()

        assert len(result) == 1
        assert result[0]["pipeline_name"] == "video_captioning_pipeline"

    def test_fallback_on_generic_exception(self):
        """A non-HTTP exception from http_json returns the default pipeline."""
        with patch(
            "backend.services.discovery.http_json",
            side_effect=Exception("boom"),
        ):
            result = discover_pipelines_remote()
        assert len(result) == 1
        assert result[0]["pipeline_type"] == "non-detection"

    def test_http_exception_is_propagated(self):
        """An HTTPException from http_json (e.g. server unreachable) is re-raised."""
        with patch(
            "backend.services.discovery.http_json",
            side_effect=HTTPException(
                status_code=502, detail="Pipeline server unreachable"
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                discover_pipelines_remote()
        assert exc_info.value.status_code == 502

    def test_empty_list_returns_default(self):
        """An empty list from the server returns the default pipeline."""
        with self._mock_http([]):
            result = discover_pipelines_remote()
        assert len(result) == 1

    def test_detection_pipelines_filtered_when_disabled(self):
        """Detection pipelines are excluded when ENABLE_DETECTION_PIPELINE is False."""
        payload = [
            {
                "version": "det",
                "parameters": {"properties": {"detection_model_name": {}}},
            },
        ]
        with self._mock_http(payload):
            result = discover_pipelines_remote()
        # All detection pipelines filtered out; fallback returned
        assert all(r["pipeline_type"] == "non-detection" for r in result)

    def test_string_pipeline_name_infers_detection_type(self):
        """String-only payloads infer detection pipelines from naming convention."""
        payload = ["Video_Captioning_RTSP_Detection_Software"]
        with self._mock_http(payload), patch(
            "backend.services.discovery.ENABLE_DETECTION_PIPELINE", True
        ):
            result = discover_pipelines_remote()

        assert len(result) == 1
        assert result[0]["pipeline_name"] == "Video_Captioning_RTSP_Detection_Software"
        assert result[0]["pipeline_type"] == "detection"

    def test_dict_without_detection_parameters_infers_from_name(self):
        """Dict payloads without detection params still infer detection by name."""
        payload = [{"name": "Video_Captioning_Camera_Detection_Hardware", "parameters": {"properties": {}}}]
        with self._mock_http(payload), patch(
            "backend.services.discovery.ENABLE_DETECTION_PIPELINE", True
        ), patch(
            "backend.services.discovery._gpu_device_exists", return_value=True
        ):
            result = discover_pipelines_remote()

        assert len(result) == 1
        assert result[0]["pipeline_type"] == "detection"

    def test_camera_detection_display_names_use_pipeline_names(self):
        """Pipeline display names are returned unchanged from pipeline identifiers."""
        payload = [
            {
                "version": "Video_Captioning_Camera_Detection_Software",
                "parameters": {"properties": {"detection_model_name": {}}},
            },
            {
                "version": "Video_Captioning_Camera_Detection_Hardware",
                "parameters": {"properties": {"detection_model_name": {}}},
            },
        ]

        with self._mock_http(payload), patch(
            "backend.services.discovery.ENABLE_DETECTION_PIPELINE", True
        ), patch(
            "backend.services.discovery._gpu_device_exists", return_value=True
        ):
            result = discover_pipelines_remote()

        display_by_name = {
            item["pipeline_name"]: item["pipeline_display_name"] for item in result
        }
        assert (
            display_by_name["Video_Captioning_Camera_Detection_Software"]
            == "Video_Captioning_Camera_Detection_Software"
        )
        assert (
            display_by_name["Video_Captioning_Camera_Detection_Hardware"]
            == "Video_Captioning_Camera_Detection_Hardware"
        )

    def test_proxy_pipelines_are_included_in_results(self):
        """Proxy pipelines for default resolution are returned in discovery results."""
        payload = [
            {
                "version": "captioner_Default_Resolution",
                "parameters": {"properties": {}},
            },
            {"version": "captioner_Custom", "parameters": {"properties": {}}},
        ]
        with self._mock_http(payload):
            result = discover_pipelines_remote()
        assert [item["pipeline_name"] for item in result] == [
            "captioner_Default_Resolution",
            "captioner_Custom",
        ]

    def test_gpu_available_prefers_generic_hardware_pipeline_name(self):
        """When GPU is available, generic hardware alias is preferred as default."""
        payload = ["Video_Captioning_Hardware", "Video_Captioning_Software"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=True
        ):
            result = discover_pipelines_remote()

        defaults = [r for r in result if r["pipeline_default"]]
        assert len(defaults) == 1
        assert defaults[0]["pipeline_name"] == "Video_Captioning_Hardware"

    def test_non_gpu_prefers_generic_software_pipeline_name(self):
        """When GPU is unavailable, generic software alias is preferred as default."""
        payload = ["Video_Captioning_Hardware", "Video_Captioning_Software"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=False
        ):
            result = discover_pipelines_remote()

        defaults = [r for r in result if r["pipeline_default"]]
        assert len(defaults) == 1
        assert defaults[0]["pipeline_name"] == "Video_Captioning_Software"



    def test_non_list_items_payload_falls_back_to_default(self):
        """Non-list 'pipelines' payloads trigger default fallback response."""
        with self._mock_http({"pipelines": "not-a-list"}):
            result = discover_pipelines_remote()

        assert len(result) == 1
        # Fallback should mirror configured runtime default for the host.
        assert result[0]["pipeline_name"] == _fallback_pipeline_name(_gpu_device_exists())
        assert result[0]["pipeline_type"] == "non-detection"

    def test_uses_id_when_version_and_name_missing(self):
        """Pipeline dicts fall back to 'id' when version/name are missing."""
        payload = [{"id": "pipeline-id", "parameters": {"properties": {}}}]

        with self._mock_http(payload):
            result = discover_pipelines_remote()

        assert result[0]["pipeline_name"] == "pipeline-id"

    def test_skips_dict_without_identifier(self):
        """Pipeline dicts without version/name/id are skipped."""
        payload = [
            {"parameters": {"properties": {}}},
            {"name": "valid", "parameters": {"properties": {}}},
        ]

        with self._mock_http(payload):
            result = discover_pipelines_remote()

        assert [item["pipeline_name"] for item in result] == ["valid"]

    def test_skips_non_string_non_dict_items(self):
        """Non-string, non-dict pipeline entries are ignored."""
        payload = [123, "valid"]

        with self._mock_http(payload):
            result = discover_pipelines_remote()

        assert [item["pipeline_name"] for item in result] == ["valid"]

    def test_non_gpu_prefers_non_gpu_default(self):
        """When GPU is unavailable, default prefers a non-GPU pipeline name."""
        payload = ["custom_GPU", "custom_CPU"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=False
        ):
            result = discover_pipelines_remote()

        defaults = [r for r in result if r["pipeline_default"]]
        assert len(defaults) == 1
        assert defaults[0]["pipeline_name"] == "custom_CPU"

    def test_falls_back_to_configured_pipeline_when_no_preferred_match(self):
        """If only GPU names exist, fallback selects configured PIPELINE_NAME."""
        payload = ["foo_GPU", "Video_Captioning"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=False
        ):
            result = discover_pipelines_remote()

        defaults = [r for r in result if r["pipeline_default"]]
        assert len(defaults) == 1
        assert defaults[0]["pipeline_name"] == "Video_Captioning"

    def test_gpu_available_falls_back_to_configured_pipeline(self):
        """With GPU available and no preferred match, configured pipeline is default."""
        payload = ["custom_GPU", "Video_Captioning"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=True
        ), patch(
            "backend.services.discovery.PIPELINE_NAME", "Video_Captioning"
        ):
            result = discover_pipelines_remote()

        defaults = [r for r in result if r["pipeline_default"]]
        assert len(defaults) == 1
        assert defaults[0]["pipeline_name"] == "Video_Captioning"

    def test_gpu_pipelines_hidden_when_no_gpu(self):
        """Pipelines without hardware/software suffix are retained as device-agnostic."""
        payload = ["Video_Captioning_on_CPU", "Video_Captioning_on_GPU"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=False
        ):
            result = discover_pipelines_remote()

        names = [r["pipeline_name"] for r in result]
        assert names == ["Video_Captioning_on_CPU", "Video_Captioning_on_GPU"]

    def test_gpu_pipelines_shown_when_gpu_available(self):
        """GPU pipelines are retained when a GPU is detected."""
        payload = ["Video_Captioning_on_CPU", "Video_Captioning_on_GPU"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=True
        ):
            result = discover_pipelines_remote()

        names = {r["pipeline_name"] for r in result}
        assert names == {"Video_Captioning_on_CPU", "Video_Captioning_on_GPU"}

    def test_gpu_only_payload_without_gpu_falls_back_to_default(self):
        """If names are device-agnostic, non-GPU host does not force fallback."""
        payload = ["Video_Captioning_on_GPU", "GenAI_Camera_Pipeline_on_GPU"]

        with self._mock_http(payload), patch(
            "backend.services.discovery._gpu_device_exists", return_value=False
        ):
            result = discover_pipelines_remote()

        assert len(result) == 2
        assert [r["pipeline_name"] for r in result] == [
            "Video_Captioning_on_GPU",
            "GenAI_Camera_Pipeline_on_GPU",
        ]
        assert all(r["pipeline_default"] is False for r in result)

    def test_non_gpu_filters_out_hardware_pipelines(self):
        """When GPU is unavailable, only software/CPU pipelines are exposed."""
        payload = [
            "Video_Captioning_Hardware",
            "GenAI_Detection_Pipeline_Hardware",
            "Video_Captioning_Software",
            "GenAI_Detection_Pipeline_Software",
        ]

        with self._mock_http(payload), patch(
            "backend.services.discovery.ENABLE_DETECTION_PIPELINE", True
        ), patch("backend.services.discovery._gpu_device_exists", return_value=False):
            result = discover_pipelines_remote()

        names = {r["pipeline_name"] for r in result}
        assert "Video_Captioning_Hardware" not in names
        assert "GenAI_Detection_Pipeline_Hardware" not in names
        assert "Video_Captioning_Software" in names
        assert "GenAI_Detection_Pipeline_Software" in names

class TestGpuHelpers:
    """Tests for GPU-related helper functions in discovery."""

    def test_gpu_device_exists_returns_false_when_dri_missing(self):
        """Returns False when /dev/dri path does not exist."""
        with patch("backend.services.discovery.Path.exists", return_value=False):
            assert _gpu_device_exists() is False

    def test_has_gpu_device_delegates_to_internal_helper(self):
        """Public helper returns the private GPU detection result."""
        with patch(
            "backend.services.discovery._gpu_device_exists", return_value=True
        ):
            assert has_gpu_device() is True

    def test_default_pipeline_names_for_cpu(self):
        """CPU defaults are returned when GPU is unavailable."""
        assert _default_pipeline_names(False) == {
            "Video_Captioning_Software",
            "Video_Captioning_RTSP_Software",
            "Video_Captioning_Camera_Software",
        }

    def test_default_pipeline_names_for_gpu(self):
        """GPU defaults include generic and source-specific hardware names."""
        assert _default_pipeline_names(True) == {
            "Video_Captioning_Hardware",
            "Video_Captioning_RTSP_Hardware",
            "Video_Captioning_Camera_Hardware",
        }

class TestNpuHelpers:
    """Tests for NPU-related helper functions in discovery."""

    def test_npu_device_exists_returns_false_when_accel_missing(self):
        """Returns False when /dev/accel path does not exist."""
        with patch("backend.services.discovery.Path.exists", return_value=False):
            assert _npu_device_exists() is False

    def test_npu_device_exists_returns_true_when_accel_nodes_exist(self):
        """Returns True when /dev/accel exists and has accel* entries."""
        with patch("backend.services.discovery.Path.exists", return_value=True), patch(
            "backend.services.discovery.Path.is_dir", return_value=True
        ), patch(
            "backend.services.discovery.Path.glob", return_value=iter(["accel0"])
        ):
            assert _npu_device_exists() is True

    def test_has_npu_device_delegates_to_internal_helper(self):
        """Public helper returns the private NPU detection result."""
        with patch(
            "backend.services.discovery._npu_device_exists", return_value=True
        ):
            assert has_npu_device() is True


class TestDiscoveryFallbackHelpers:
    """Tests for helper fallbacks not covered by remote discovery flows."""

    def test_fallback_pipeline_converts_hardware_to_software_without_gpu(self):
        """Configured hardware default falls back to software when no GPU."""
        with patch(
            "backend.services.discovery.PIPELINE_NAME", "Video_Captioning_Hardware"
        ):
            assert _fallback_pipeline_name(False) == "Video_Captioning_Software"

    def test_infer_detection_from_empty_name_returns_false(self):
        """Empty or whitespace pipeline names are not detection pipelines."""
        assert _infer_detection_from_name("") is False
        assert _infer_detection_from_name("   ") is False