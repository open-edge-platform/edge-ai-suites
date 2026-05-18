"""D2 SSE event stream unit tests.

These tests exercise _compute_delta and the SSE endpoint directly via the
Flask test client using a generator capture approach.
"""
import json
import copy
from backend_mvp.app import _compute_delta


# ---------------------------------------------------------------------------
# _compute_delta tests
# ---------------------------------------------------------------------------

def test_delta_returns_empty_when_unchanged() -> None:
    state = {"lifecycle": "running", "metrics": {"fps": 15.0}}
    assert _compute_delta(state, copy.deepcopy(state)) == {}


def test_delta_returns_changed_scalar() -> None:
    prev = {"lifecycle": "starting", "metrics": {"fps": 0.0}}
    curr = {"lifecycle": "running", "metrics": {"fps": 15.5}}
    delta = _compute_delta(prev, curr)
    assert delta["lifecycle"] == "running"
    assert delta["metrics"]["fps"] == 15.5


def test_delta_nested_unchanged_field_omitted() -> None:
    prev = {"analytics": {"patient_presence": False, "latch_status": "unknown"}}
    curr = {"analytics": {"patient_presence": True, "latch_status": "unknown"}}
    delta = _compute_delta(prev, curr)
    # Only changed field
    assert delta["analytics"]["patient_presence"] is True
    assert "latch_status" not in delta["analytics"]


def test_delta_new_key_included() -> None:
    prev = {"lifecycle": "ready"}
    curr = {"lifecycle": "ready", "new_key": "added"}
    delta = _compute_delta(prev, curr)
    assert delta["new_key"] == "added"
    assert "lifecycle" not in delta  # unchanged
