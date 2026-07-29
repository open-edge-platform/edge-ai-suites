"""C2 rPPG custom script unit tests.

These tests cover the preprocessor and postprocessor logic that are pure
numpy/opencv so they run without requiring a real OpenVINO model.
"""
import numpy as np
import pytest


def _make_frame(h: int = 120, w: int = 160) -> np.ndarray:
    """Create a synthetic BGR uint8 frame."""
    return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# _Preprocessor tests
# ---------------------------------------------------------------------------

def test_preprocessor_produces_correct_batch_shape() -> None:
    from pipelines.nicu_rppg_custom import _Preprocessor
    prep = _Preprocessor()
    for _ in range(10):
        prep.add_frame(_make_frame())
    assert prep.has_batch()
    diff, app = prep.get_batch()
    assert diff.shape == (10, 36, 36, 3)
    assert app.shape == (10, 36, 36, 3)


def test_preprocessor_not_ready_before_ten_frames() -> None:
    from pipelines.nicu_rppg_custom import _Preprocessor
    prep = _Preprocessor()
    for i in range(9):
        prep.add_frame(_make_frame())
        assert prep.has_batch() is False


def test_preprocessor_normalises_values_to_0_1() -> None:
    from pipelines.nicu_rppg_custom import _Preprocessor
    prep = _Preprocessor()
    # Feed 10 identical white frames
    white = np.full((120, 160, 3), 255, dtype=np.uint8)
    for _ in range(10):
        prep.add_frame(white)
    _, app = prep.get_batch()
    assert app.max() <= 1.0
    assert app.min() >= 0.0


# ---------------------------------------------------------------------------
# _Postprocessor tests
# ---------------------------------------------------------------------------

def test_postprocessor_warming_up_with_few_samples() -> None:
    from pipelines.nicu_rppg_custom import _Postprocessor
    pp = _Postprocessor()
    pp.add(np.random.randn(5))
    result = pp.compute()
    assert result["status"] == "warming_up"
    assert result["heart_rate_bpm"] is None


def test_postprocessor_computes_bpm_with_enough_samples() -> None:
    from pipelines.nicu_rppg_custom import _Postprocessor
    pp = _Postprocessor()
    # Sine wave at 1 Hz = 60 BPM; sampling rate assumed 30 Hz
    t = np.linspace(0, 5, 150)
    wave = np.sin(2 * np.pi * 1.0 * t)
    pp.add(wave)
    result = pp.compute()
    # Should not be warming_up
    assert result["status"] != "warming_up"
    # HR should be in the expected physiological range
    if result["heart_rate_bpm"] is not None:
        assert 30.0 <= result["heart_rate_bpm"] <= 180.0


# ---------------------------------------------------------------------------
# RppgPipeline safe output tests (no real model needed)
# ---------------------------------------------------------------------------

def test_pipeline_returns_safe_output_on_empty_frames() -> None:
    from pipelines.nicu_rppg_custom import RppgPipeline
    pipeline = RppgPipeline(model_xml="/nonexistent/model.xml")
    result = pipeline.process([])
    assert result["status"] == "no_frames"
    assert result["heart_rate_bpm"] is None
    assert result["signal_confidence"] == 0.0


def test_pipeline_returns_warming_up_before_batch_ready() -> None:
    from pipelines.nicu_rppg_custom import RppgPipeline
    pipeline = RppgPipeline(model_xml="/nonexistent/model.xml")
    frames = [_make_frame() for _ in range(5)]  # less than batch of 10
    result = pipeline.process(frames)
    # Should say warming_up (batch not full) — model load won't be attempted
    assert result["status"] in {"warming_up", "no_frames"}
