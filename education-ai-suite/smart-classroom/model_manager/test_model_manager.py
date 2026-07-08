import threading
import sys
import os

# Ensure smart-classroom root is on sys.path so components.ocr is importable
# when tests are run from the model_manager/ directory.
_SC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from model_manager import ModelManager
from components.ocr.ocr_handle import OcrHandler
from model_manager.capability_state import CapabilityState


def test_instance_returns_same_object():
    assert ModelManager.instance() is ModelManager.instance()


def test_constructor_returns_same_object():
    assert ModelManager() is ModelManager()


def test_instance_thread_safe():
    results = []

    def collect():
        results.append(ModelManager.instance())

    threads = [threading.Thread(target=collect) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    first = results[0]
    assert all(obj is first for obj in results)


def test_placeholder_methods():
    mgr = ModelManager.instance()

    for method in (mgr.text_gen, mgr.asr):
        try:
            method()
            assert False, "expected NotImplementedError"
        except NotImplementedError:
            pass

    assert mgr.warmup([]) is None
    assert mgr.shutdown() is None


def test_health_reports_ocr_state_without_loading():
    mgr = ModelManager.instance()
    mgr.shutdown()  # ensure not loaded

    health = mgr.health()
    assert "ocr" in health
    ocr = health["ocr"]
    assert ocr["state"] == "unloaded"
    assert ocr["loaded"] is False
    assert ocr["max_concurrency"] == 2
    # device and provider are None before the handler is loaded
    assert ocr["device"] is None
    assert ocr["provider"] is None
    # memory key absent when not loaded
    assert "memory" not in ocr


def test_health_memory_key_present_when_loaded():
    from unittest.mock import MagicMock, patch

    mgr = ModelManager.instance()
    mgr.shutdown()

    # Inject a mock handler that reports loaded state and memory
    mock_handler = MagicMock()
    mock_handler.loaded = True
    mock_handler.state.value = "ready"
    mock_handler.provider = "paddle"
    mock_handler.device = "CPU"
    mock_handler.max_concurrency = 2
    mock_handler.memory_stats.return_value = {"process_rss_mb": 512.0}

    mgr._ocr_handler = mock_handler

    health = mgr.health()
    ocr = health["ocr"]
    assert ocr["state"] == "ready"
    assert ocr["loaded"] is True
    assert ocr["device"] == "CPU"
    assert ocr["provider"] == "paddle"
    assert "memory" in ocr
    assert "process_rss_mb" in ocr["memory"]

    # cleanup
    mgr.shutdown()


# ---------------------------------------------------------------------------
# OcrHandler state machine
# ---------------------------------------------------------------------------

def _make_handler_with_mock_processor():
    """Return an OcrHandler whose _build_processor is patched out."""
    from unittest.mock import MagicMock, patch
    handler = OcrHandler()
    mock_processor = MagicMock()
    mock_processor.extract_text.return_value = "text"
    return handler, mock_processor


def test_ocr_handler_initial_state_is_unloaded():
    handler = OcrHandler()
    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_ocr_handler_state_transitions_unloaded_to_ready():
    from unittest.mock import MagicMock, patch
    handler = OcrHandler()
    mock_processor = MagicMock()
    mock_processor.extract_text.return_value = "text"

    with patch.object(handler, "_build_processor", return_value=mock_processor):
        handler.load()

    assert handler.state == CapabilityState.READY
    assert handler.loaded is True

    handler.shutdown()
    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_ocr_handler_state_reverts_on_load_failure():
    from unittest.mock import patch
    handler = OcrHandler()

    with patch.object(handler, "_build_processor", side_effect=RuntimeError("load failed")):
        try:
            handler.load()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_ocr_handler_reads_concurrency_from_config():
    """7.1 — concurrency and queue_max come from config, not hard-coded constants."""
    from unittest.mock import MagicMock, patch
    handler = OcrHandler()
    mock_processor = MagicMock()
    mock_processor.extract_text.return_value = "text"

    with patch.object(handler, "_build_processor", return_value=mock_processor):
        with patch.object(handler, "_concurrency_config", return_value=(3, 20)):
            handler.load()

    # max_concurrency property reflects the config value, not the module constant
    assert handler.max_concurrency == 3
    # the CapabilityRunner itself was built with the config-driven queue_max
    assert handler._runner._queue_max == 20

    handler.shutdown()

