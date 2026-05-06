"""D3 FrameService unit tests."""
import time
from backend_mvp.frame_service import FrameService


def test_frame_service_returns_none_before_first_frame() -> None:
    svc = FrameService()
    frame, fresh = svc.get_latest()
    assert frame is None
    assert fresh is False
    assert svc.is_fresh() is False


def test_frame_service_fresh_after_update() -> None:
    svc = FrameService(max_age_seconds=5.0)
    svc.update(b"\xff\xd8\xff")  # minimal JPEG header
    frame, fresh = svc.get_latest()
    assert frame == b"\xff\xd8\xff"
    assert fresh is True
    assert svc.is_fresh() is True


def test_frame_service_stale_after_max_age() -> None:
    svc = FrameService(max_age_seconds=0.01)
    svc.update(b"\xff\xd8\xff")
    time.sleep(0.05)
    _, fresh = svc.get_latest()
    assert fresh is False


def test_frame_service_clear_removes_frame() -> None:
    svc = FrameService()
    svc.update(b"data")
    svc.clear()
    frame, fresh = svc.get_latest()
    assert frame is None
    assert fresh is False
