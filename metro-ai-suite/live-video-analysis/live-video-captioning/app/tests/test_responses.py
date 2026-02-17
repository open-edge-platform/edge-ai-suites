# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.models.responses, Pydantic response models."""

import pytest
from pydantic import ValidationError
from backend.models.responses import (
    RunInfo,
    ModelList,
    PipelineInfo,
    PipelineInfoList,
)


class TestRunInfo:
    """RunInfo model construction and optional fields."""

    def test_required_fields_only(self):
        """RunInfo can be created with only the required fields."""
        info = RunInfo(
            runId="abc",
            pipelineId="p1",
            peerId="peer1",
            mqttTopic="topic/abc",
        )
        assert info.runId == "abc"
        assert info.modelName is None
        assert info.runName is None

    def test_all_fields(self):
        """RunInfo accepts every optional field."""
        info = RunInfo(
            runId="abc",
            pipelineId="p1",
            peerId="peer1",
            mqttTopic="topic/abc",
            modelName="model-a",
            pipelineName="pipe-a",
            runName="my_run",
            prompt="describe",
            maxTokens=100,
            rtspUrl="rtsp://10.0.0.1/s",
        )
        assert info.modelName == "model-a"
        assert info.maxTokens == 100
        assert info.rtspUrl == "rtsp://10.0.0.1/s"

    def test_serialization_roundtrip(self):
        """RunInfo serialises to dict and back without data loss."""
        info = RunInfo(
            runId="r1",
            pipelineId="p1",
            peerId="peer1",
            mqttTopic="t/r1",
            modelName="m",
        )
        data = info.model_dump()
        restored = RunInfo(**data)
        assert restored == info


class TestModelList:
    """ModelList model."""

    def test_empty_model_list(self):
        """An empty list of models is valid."""
        ml = ModelList(models=[])
        assert ml.models == []

    def test_populated_model_list(self):
        """ModelList stores an ordered list of model names."""
        ml = ModelList(models=["InternVL2-1B", "InternVL2-2B"])
        assert len(ml.models) == 2
        assert ml.models[0] == "InternVL2-1B"


class TestPipelineInfo:
    """PipelineInfo model with literal type constraint."""

    def test_detection_type(self):
        """pipeline_type 'detection' is accepted."""
        p = PipelineInfo(pipeline_name="det_pipe", pipeline_type="detection")
        assert p.pipeline_type == "detection"

    def test_non_detection_type(self):
        """pipeline_type 'non-detection' is accepted."""
        p = PipelineInfo(pipeline_name="gen_pipe", pipeline_type="non-detection")
        assert p.pipeline_type == "non-detection"

    def test_invalid_type_rejected(self):
        """An unsupported pipeline_type raises a validation error."""
        with pytest.raises(ValidationError):
            PipelineInfo(pipeline_name="x", pipeline_type="unknown")


class TestPipelineInfoList:
    """PipelineInfoList wrapper."""

    def test_empty_list(self):
        """An empty pipeline list is valid."""
        pl = PipelineInfoList(pipelines=[])
        assert pl.pipelines == []

    def test_mixed_pipeline_types(self):
        """A list may contain both detection and non-detection pipelines."""
        pl = PipelineInfoList(
            pipelines=[
                PipelineInfo(pipeline_name="a", pipeline_type="detection"),
                PipelineInfo(pipeline_name="b", pipeline_type="non-detection"),
            ]
        )
        assert len(pl.pipelines) == 2
