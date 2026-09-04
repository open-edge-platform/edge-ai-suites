from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.mocks.pipeline import make_pipeline_mock
from tests.mocks.va_service import make_va_service_mock, make_wait_completion_mock
from tests.mocks.board_ocr import make_board_ocr_mocks


@pytest.fixture(scope="session")
def app():
    from main import app as _app
    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _mock_orchestrator():
    """Route every orchestrator's external interaction through placeholder mocks.

    Keeps the orchestration logic (threads, stage ordering, DB state machine)
    real while replacing the heavy concrete work.  Individual tests may still
    reach into utils.orchestrator to tune a specific mock's side effect.
    """
    pipeline = make_pipeline_mock()
    va_service = make_va_service_mock()
    wait_completion = make_wait_completion_mock()
    start_ocr, stop_ocr = make_board_ocr_mocks()

    with patch("utils.orchestrator.Pipeline", return_value=pipeline), \
         patch("utils.orchestrator.VideoAnalyticsPipelineService", return_value=va_service), \
         patch("utils.orchestrator.wait_for_va_completion", wait_completion), \
         patch("utils.orchestrator.StorageManager.wait_idle"), \
         patch("components.board_ocr.board_ocr_pipeline.start_board_ocr", start_ocr), \
         patch("components.board_ocr.board_ocr_pipeline.stop_board_ocr", stop_ocr):
        yield {
            "pipeline": pipeline,
            "va_service": va_service,
            "wait_completion": wait_completion,
            "start_ocr": start_ocr,
            "stop_ocr": stop_ocr,
        }


def wait_for_state(client, session_id, timeout=5.0):
    from utils import orchestrator
    import time
    deadline = time.monotonic() + timeout
    terminal = {"completed", "failed", "cancelled"}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/sessions/{session_id}/status")
        state = resp.json().get("state")
        if state in terminal and session_id not in orchestrator._RUNNING:
            return state
        time.sleep(0.05)
    raise TimeoutError(
        f"session {session_id} did not reach terminal state within {timeout}s"
    )