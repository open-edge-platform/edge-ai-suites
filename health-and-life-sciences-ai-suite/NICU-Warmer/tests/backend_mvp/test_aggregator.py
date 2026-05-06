"""D1 aggregator unit tests."""
from backend_mvp.aggregator import RuntimeAggregator


def test_aggregator_normalises_presence_booleans() -> None:
    agg = RuntimeAggregator()
    result = agg.normalize(
        {"patient_presence": 1, "caretaker_presence": 0, "latch_status": "latched"}
    )
    assert result["analytics"]["patient_presence"] is True
    assert result["analytics"]["caretaker_presence"] is False
    assert result["analytics"]["latch_status"] == "latched"


def test_aggregator_maps_latch_status_unknown_default() -> None:
    agg = RuntimeAggregator()
    result = agg.normalize({})
    assert result["analytics"]["latch_status"] == "unknown"
    assert result["analytics"]["patient_presence"] is False


def test_aggregator_preserves_rppg_output_schema() -> None:
    agg = RuntimeAggregator()
    rppg = {"heart_rate_bpm": 72.5, "respiration_rate_bpm": 16.0, "signal_confidence": 0.88, "status": "valid"}
    result = agg.normalize({}, rppg_output=rppg)
    assert result["rppg"]["heart_rate_bpm"] == 72.5
    assert result["rppg"]["respiration_rate_bpm"] == 16.0
    assert result["rppg"]["signal_confidence"] == 0.88
    assert result["rppg"]["status"] == "valid"


def test_aggregator_handles_missing_rppg_gracefully() -> None:
    agg = RuntimeAggregator()
    result = agg.normalize({"patient_presence": True})
    assert result["rppg"]["heart_rate_bpm"] is None
    assert result["rppg"]["status"] == "idle"
    assert result["rppg"]["signal_confidence"] == 0.0
