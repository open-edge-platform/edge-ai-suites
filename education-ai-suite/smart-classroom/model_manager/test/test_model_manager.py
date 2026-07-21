import threading
import sys
import os

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from model_manager import ModelManager
from components.ocr.ocr_handle import OcrHandler
from components.asr.asr_handle import AsrHandler
from model_manager.capability.state import CapabilityState


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
    for method in (mgr.ocr_vlm,):
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


# ---------------------------------------------------------------------------
# AsrHandler state machine
# ---------------------------------------------------------------------------

def test_asr_handler_initial_state_is_unloaded():
    handler = AsrHandler()
    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_asr_handler_state_transitions_unloaded_to_ready():
    from unittest.mock import MagicMock, patch
    handler = AsrHandler()
    mock_processor = MagicMock()
    mock_processor.transcribe.return_value = "transcribed text"

    with patch.object(handler, "_build_processor", return_value=mock_processor):
        handler.load()

    assert handler.state == CapabilityState.READY
    assert handler.loaded is True

    handler.shutdown()
    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_asr_handler_state_reverts_on_load_failure():
    from unittest.mock import patch
    handler = AsrHandler()

    with patch.object(handler, "_build_processor", side_effect=RuntimeError("load failed")):
        try:
            handler.load()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_asr_handler_reads_concurrency_from_config():
    """ASR concurrency and queue_max come from config."""
    from unittest.mock import MagicMock, patch
    handler = AsrHandler()
    mock_processor = MagicMock()
    mock_processor.transcribe.return_value = "text"

    with patch.object(handler, "_build_processor", return_value=mock_processor):
        with patch.object(handler, "_concurrency_config", return_value=(2, 16)):
            handler.load()

    assert handler.max_concurrency == 2
    assert handler._runner._queue_max == 16

    handler.shutdown()


def test_health_reports_asr_state_without_loading():
    mgr = ModelManager.instance()
    mgr.shutdown()  # ensure not loaded

    health = mgr.health()
    assert "asr" in health
    asr = health["asr"]
    assert asr["state"] == "unloaded"
    assert asr["loaded"] is False
    assert asr["max_concurrency"] == 1
    assert asr["device"] is None
    assert asr["provider"] is None
    assert "memory" not in asr


def test_health_asr_memory_key_present_when_loaded():
    from unittest.mock import MagicMock, patch

    mgr = ModelManager.instance()
    mgr.shutdown()

    # Inject a mock ASR handler
    mock_handler = MagicMock()
    mock_handler.loaded = True
    mock_handler.state.value = "ready"
    mock_handler.provider = "openai"
    mock_handler.device = "CPU"
    mock_handler.max_concurrency = 1
    mock_handler.memory_stats.return_value = {"process_rss_mb": 1024.0}

    mgr._asr_handler = mock_handler

    health = mgr.health()
    asr = health["asr"]
    assert asr["state"] == "ready"
    assert asr["loaded"] is True
    assert asr["device"] == "CPU"
    assert asr["provider"] == "openai"
    assert "memory" in asr
    assert "process_rss_mb" in asr["memory"]

    # cleanup
    mgr.shutdown()


def test_text_gen_returns_handler_and_does_not_raise():
    """text_gen() is implemented — it returns a handler, never NotImplementedError."""
    mgr = ModelManager.instance()
    mgr.shutdown()

    handler = mgr.text_gen()
    assert handler is not None
    assert hasattr(handler, "generate")
    # idempotent: the same warm handler is returned on repeat calls
    assert mgr.text_gen() is handler

    mgr.shutdown()


def test_health_reports_text_gen_state_without_loading():
    mgr = ModelManager.instance()
    mgr.shutdown()  # ensure not loaded

    health = mgr.health()
    assert "text_gen" in health
    tg = health["text_gen"]
    assert tg["state"] == "unloaded"
    assert tg["loaded"] is False
    assert tg["max_concurrency"] == 1
    # device and provider are None before the handler is loaded
    assert tg["device"] is None
    assert tg["provider"] is None
    # memory key absent when not loaded
    assert "memory" not in tg


def test_health_text_gen_memory_key_present_when_loaded():
    from unittest.mock import MagicMock

    mgr = ModelManager.instance()
    mgr.shutdown()

    # Inject a mock handler that reports loaded state and memory
    mock_handler = MagicMock()
    mock_handler.loaded = True
    mock_handler.state.value = "ready"
    mock_handler.provider = "vlm"
    mock_handler.device = "GPU"
    mock_handler.max_concurrency = 1
    mock_handler.memory_stats.return_value = {"process_rss_mb": 2048.0}

    mgr._text_gen_handler = mock_handler

    health = mgr.health()
    tg = health["text_gen"]
    assert tg["state"] == "ready"
    assert tg["loaded"] is True
    assert tg["device"] == "GPU"
    assert tg["provider"] == "vlm"
    assert "memory" in tg
    assert "process_rss_mb" in tg["memory"]

    mgr.shutdown()


def test_shutdown_evicts_text_gen_handler():
    from unittest.mock import MagicMock

    mgr = ModelManager.instance()
    mock_handler = MagicMock()
    mgr._text_gen_handler = mock_handler

    mgr.shutdown()

    mock_handler.shutdown.assert_called_once()
    assert mgr._text_gen_handler is None


# ---------------------------------------------------------------------------
# TextGenHandler state machine (mirrors OcrHandler)
# ---------------------------------------------------------------------------

def _mock_vlm():
    from unittest.mock import MagicMock
    vlm = MagicMock()
    vlm.device = "GPU"
    vlm.generate.return_value = "hello"
    return vlm


def test_text_gen_handler_initial_state_is_unloaded():
    from components.vlm.text_gen_handle import TextGenHandler
    handler = TextGenHandler()
    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_text_gen_handler_state_transitions_unloaded_to_ready():
    from unittest.mock import patch
    from components.vlm.text_gen_handle import TextGenHandler
    handler = TextGenHandler()

    with patch.object(handler, "_build_vlm", return_value=_mock_vlm()):
        handler.load()

    assert handler.state == CapabilityState.READY
    assert handler.loaded is True

    handler.shutdown()
    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_text_gen_handler_state_reverts_on_load_failure():
    from unittest.mock import patch
    from components.vlm.text_gen_handle import TextGenHandler
    handler = TextGenHandler()

    with patch.object(handler, "_build_vlm", side_effect=RuntimeError("load failed")):
        try:
            handler.load()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    assert handler.state == CapabilityState.UNLOADED
    assert handler.loaded is False


def test_text_gen_handler_reads_concurrency_from_config():
    """Concurrency and queue_max come from config, not hard-coded constants."""
    from unittest.mock import patch
    from components.vlm.text_gen_handle import TextGenHandler
    handler = TextGenHandler()

    with patch.object(handler, "_build_vlm", return_value=_mock_vlm()):
        with patch.object(handler, "_concurrency_config", return_value=(2, 12)):
            handler.load()

    # handler surfaces the config-driven concurrency, and the runner was built
    # with the config-driven queue_max
    assert handler.max_concurrency == 2
    assert handler._runner._queue_max == 12

    handler.shutdown()


def test_text_gen_handler_generate_routes_through_runner():
    """generate() serializes through the CapabilityRunner with the kwarg contract."""
    from unittest.mock import patch
    from components.vlm.text_gen_handle import TextGenHandler
    handler = TextGenHandler()
    vlm = _mock_vlm()

    with patch.object(handler, "_build_vlm", return_value=vlm):
        handler.load()
        out = handler.generate("hi", stream=False)

    assert out == "hello"
    vlm.generate.assert_called_once()
    args, kwargs = vlm.generate.call_args
    assert args[0] == "hi"
    assert kwargs.get("stream") is False
    assert kwargs.get("images") is None

    handler.shutdown()
