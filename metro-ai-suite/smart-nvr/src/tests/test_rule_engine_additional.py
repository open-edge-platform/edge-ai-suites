"""Additional tests for rule_engine.process_event to raise coverage.

Exercises matching, non-matching, source mismatch, count thresholds (pedestrian & vehicle),
and successful dispatch + store paths.
"""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_process_event_rule_match_without_threshold():
    from service import rule_engine
    event = {"label": "car", "camera": "garage"}
    rules = [
        {"id": "r1", "label": "car", "camera": "garage", "action": "summarize"},
        {"id": "r2", "label": "person", "camera": "garage", "action": "summarize"},  # no match
    ]

    with patch("service.rule_engine.get_rules", AsyncMock(return_value=rules)), \
         patch("service.rule_engine.dispatch_action", AsyncMock(return_value={"ok": True})) as dispatch, \
         patch("service.rule_engine.store_response", AsyncMock()) as store:
        await rule_engine.process_event(event, context={"source": None})
        dispatch.assert_awaited_once()
        store.assert_awaited_once()
        # event mutated with rule_id before dispatch
        assert event.get("rule_id") == "r1"

@pytest.mark.asyncio
async def test_process_event_source_mismatch_skips():
    from service import rule_engine
    event = {"label": "car", "camera": "garage"}
    rules = [
        {"id": "r1", "label": "car", "camera": "garage", "action": "summarize", "source": "frigate"},
    ]
    with patch("service.rule_engine.get_rules", AsyncMock(return_value=rules)), \
         patch("service.rule_engine.dispatch_action", AsyncMock()) as dispatch:
        await rule_engine.process_event(event, context={"source": "scenescape"})
        dispatch.assert_not_called()
        assert "rule_id" not in event

@pytest.mark.asyncio
async def test_process_event_threshold_vehicle_pass_and_fail():
    from service import rule_engine
    # First rule passes threshold, second fails
    rules = [
        {"id": "r_pass", "label": "car", "camera": "garage", "action": "summarize", "count": 2},
        {"id": "r_fail", "label": "car", "camera": "garage", "action": "summarize", "count": 5},
    ]
    event = {"label": "car", "camera": "garage", "num_vehicles": 3}
    with patch("service.rule_engine.get_rules", AsyncMock(return_value=rules)), \
         patch("service.rule_engine.dispatch_action", AsyncMock(return_value={"done": True})) as dispatch, \
         patch("service.rule_engine.store_response", AsyncMock()) as store:
        await rule_engine.process_event(event)
        # Only first matching rule should dispatch
        assert dispatch.await_count == 1
        assert store.await_count == 1
        assert event.get("rule_id") == "r_pass"

@pytest.mark.asyncio
async def test_process_event_threshold_pedestrian_missing_and_present():
    from service import rule_engine
    # One rule with threshold but event missing count -> skip
    # Another rule with count and event count present -> dispatch
    # First rule has higher threshold than provided count -> skipped.
    # Second rule passes -> dispatched.
    rules = [
        {"id": "r_skip", "label": "pedestrian", "camera": "front", "action": "search", "count": 5},
        {"id": "r_ok", "label": "pedestrian", "camera": "front", "action": "search", "count": 2},
    ]
    # Provide count only second time by running two events
    event_missing = {"label": "pedestrian", "camera": "front"}
    event_present = {"label": "pedestrian", "camera": "front", "num_pedestrians": 3}
    with patch("service.rule_engine.get_rules", AsyncMock(return_value=rules)), \
         patch("service.rule_engine.dispatch_action", AsyncMock(return_value={"result": "ok"})) as dispatch, \
         patch("service.rule_engine.store_response", AsyncMock()) as store:
        await rule_engine.process_event(event_missing)
        await rule_engine.process_event(event_present)
        # Only second event triggers dispatch
        assert dispatch.await_count == 1
        assert event_present.get("rule_id") == "r_ok"
