# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for dispatcher action handling."""
import pytest
from types import SimpleNamespace

# We import the dispatcher module after monkeypatching its dependencies where needed.

@pytest.mark.asyncio
async def test_dispatcher_summarize_success(monkeypatch):
    # Prepare fake services / persistence
    async def fake_save_summary_id(rule_id, summary_id):
        assert rule_id == "r1"
        assert summary_id == "sum123"

    async def fake_save_summary_result(summary_id, result):
        assert summary_id == "sum123"
        assert result == "Summary text"

    class FakeVms:
        async def summarize(self, camera_name, start_time, end_time):
            return {"status": 200, "message": "sum123"}
        def summary(self, summary_id):
            return {"summary": "Summary text"}

    monkeypatch.setattr("service.dispatcher.vms_service", FakeVms())
    monkeypatch.setattr("service.dispatcher.save_summary_id", fake_save_summary_id)
    monkeypatch.setattr("service.dispatcher.save_summary_result", fake_save_summary_result)

    from service.dispatcher import dispatch_action

    event = {"camera": "cam1", "start_time": 1.0, "end_time": 2.0, "rule_id": "r1"}
    result = await dispatch_action("summarize", event)
    assert result["summary_id"] == "sum123"
    assert result["result"] == "Summary text"


@pytest.mark.asyncio
async def test_dispatcher_summarize_validation_error(monkeypatch):
    from service.dispatcher import dispatch_action
    event = {"camera": None, "start_time": 1.0, "end_time": 2.0, "rule_id": "r1"}
    out = await dispatch_action("summarize", event)
    assert "error" in out
    assert "Missing required" in out["error"]


@pytest.mark.asyncio
async def test_dispatcher_summarize_non_200(monkeypatch):
    class FakeVms:
        async def summarize(self, *a, **k):
            return {"status": 500, "message": "failure"}
        def summary(self, summary_id):
            return {"summary": "Should not be used"}

    monkeypatch.setattr("service.dispatcher.vms_service", FakeVms())
    from service.dispatcher import dispatch_action
    event = {"camera": "cam1", "start_time": 1, "end_time": 2, "rule_id": "r1"}
    out = await dispatch_action("summarize", event)
    # Non-200 path returns None
    assert out is None


@pytest.mark.asyncio
async def test_dispatcher_search_success(monkeypatch):
    async def fake_save_search(rule_id, output):
        assert rule_id == "r2"
        assert output["status"] == 200

    class FakeVms:
        async def search_embeddings(self, camera_name, start_time, end_time):
            return {"status": 200, "result": "ok"}

    monkeypatch.setattr("service.dispatcher.vms_service", FakeVms())
    monkeypatch.setattr("service.dispatcher.save_search", fake_save_search)

    from service.dispatcher import dispatch_action
    event = {"camera": "camA", "start_time": 5, "end_time": 6, "rule_id": "r2"}
    out = await dispatch_action("add to search", event)
    assert out == {"status": 200, "result": "ok"}


@pytest.mark.asyncio
async def test_dispatcher_search_validation_error(monkeypatch):
    from service.dispatcher import dispatch_action
    event = {"camera": None, "start_time": 1, "end_time": 2, "rule_id": "r2"}
    out = await dispatch_action("add to search", event)
    assert "error" in out
    assert "Missing required" in out["error"]


@pytest.mark.asyncio
async def test_dispatcher_unknown_action():
    from service.dispatcher import dispatch_action
    out = await dispatch_action("not-real", {"rule_id": "x"})
    assert out == {"error": "Unknown action: not-real"}
