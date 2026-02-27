# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.state, in-memory run storage."""

from backend.models.responses import RunInfo
from backend.state import RUNS


class TestRunsState:
    """Verify basic dict operations on the global RUNS store."""

    def test_runs_starts_empty(self):
        """RUNS dict is empty at the start of each test (cleared by fixture)."""
        assert RUNS == {}

    def test_add_and_retrieve_run(self):
        """A RunInfo entry can be stored and retrieved by run ID."""
        info = RunInfo(
            runId="r1",
            pipelineId="p1",
            peerId="peer1",
            mqttTopic="topic/r1",
        )
        RUNS["r1"] = info
        assert RUNS["r1"].runId == "r1"
        assert RUNS["r1"].pipelineId == "p1"

    def test_remove_run(self):
        """Removing a run by key clears it from the store."""
        RUNS["r2"] = RunInfo(
            runId="r2",
            pipelineId="p2",
            peerId="peer2",
            mqttTopic="topic/r2",
        )
        RUNS.pop("r2", None)
        assert "r2" not in RUNS

    def test_multiple_runs(self):
        """Multiple runs can coexist in the store."""
        for i in range(3):
            RUNS[f"run-{i}"] = RunInfo(
                runId=f"run-{i}",
                pipelineId=f"p-{i}",
                peerId=f"peer-{i}",
                mqttTopic=f"topic/run-{i}",
            )
        assert len(RUNS) == 3
