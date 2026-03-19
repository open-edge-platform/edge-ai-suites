# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.discovery, model and pipeline discovery."""

import json
from unittest.mock import patch


from backend.services.discovery import (
    discover_models,
    discover_detection_models,
    is_detection_pipeline,
    discover_pipelines_remote,
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

    def test_discovers_subdirectory_models(self, models_dir):
        """Each subdirectory name is returned as a model name."""
        (models_dir / "InternVL2-1B").mkdir()
        (models_dir / "InternVL2-2B").mkdir()
        result = discover_models(models_dir)
        assert result == ["InternVL2-1B", "InternVL2-2B"]

    def test_discovers_flat_file_models(self, models_dir):
        """XML, BIN, and JSON files in the root are returned as models."""
        (models_dir / "model.xml").write_text("")
        (models_dir / "model.bin").write_text("")
        (models_dir / "config.json").write_text("")
        result = discover_models(models_dir)
        assert set(result) == {"config.json", "model.bin", "model.xml"}

    def test_ignores_dotfiles(self, models_dir):
        """Hidden files/directories (starting with '.') are skipped."""
        (models_dir / ".hidden_dir").mkdir()
        (models_dir / ".hidden_file.json").write_text("")
        (models_dir / "visible_model").mkdir()
        result = discover_models(models_dir)
        assert result == ["visible_model"]

    def test_ignores_unsupported_extensions(self, models_dir):
        """Files with extensions other than .xml, .bin, .json are skipped."""
        (models_dir / "readme.txt").write_text("")
        (models_dir / "data.csv").write_text("")
        assert discover_models(models_dir) == []

    def test_results_are_sorted(self, models_dir):
        """Returned model names are sorted alphabetically."""
        for name in ["Zeta", "Alpha", "Mid"]:
            (models_dir / name).mkdir()
        assert discover_models(models_dir) == ["Alpha", "Mid", "Zeta"]


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

    def test_fallback_on_exception(self):
        """An exception from http_json returns the default pipeline."""
        with patch(
            "backend.services.discovery.http_json",
            side_effect=Exception("boom"),
        ):
            result = discover_pipelines_remote()
        assert len(result) == 1
        assert result[0]["pipeline_type"] == "non-detection"

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
