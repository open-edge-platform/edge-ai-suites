"""CUDA -> XPU compatibility shim for Ultralytics 8.4.x on PyTorch 2.7+xpu.

Importing this module monkey-patches ``torch.cuda.{get_device_properties,
get_device_name, empty_cache, memory_reserved}`` so Ultralytics' trainer
loop (``_clear_memory``, ``check_amp``) works with an XPU device.

Must be imported BEFORE ``from ultralytics import YOLO``.

Ported verbatim from poc/st2_app/trainer/xpu_compat.py.
"""
import torch

_get_props = torch.cuda.get_device_properties
_get_name = torch.cuda.get_device_name
_empty = torch.cuda.empty_cache
_mem_res = torch.cuda.memory_reserved


def _is_xpu(d):
    if isinstance(d, torch.device):
        return d.type == "xpu"
    if isinstance(d, str):
        return d.startswith("xpu")
    return False


def _shim_props(device=0):
    if _is_xpu(device):
        return torch.xpu.get_device_properties(device)
    try:
        return _get_props(device)
    except Exception:
        if torch.xpu.is_available():
            return torch.xpu.get_device_properties(0)
        raise


def _shim_name(device=0):
    if _is_xpu(device):
        return torch.xpu.get_device_name(device)
    try:
        return _get_name(device)
    except Exception:
        if torch.xpu.is_available():
            return torch.xpu.get_device_name(0)
        raise


def _shim_empty():
    if torch.xpu.is_available():
        try:
            torch.xpu.empty_cache()
        except Exception:
            pass


def _shim_mem_res(device=None):
    if torch.xpu.is_available():
        try:
            return (
                torch.xpu.memory_reserved(device)
                if device is not None
                else torch.xpu.memory_reserved()
            )
        except Exception:
            return 0
    return 0


torch.cuda.get_device_properties = _shim_props
torch.cuda.get_device_name = _shim_name
torch.cuda.empty_cache = _shim_empty
torch.cuda.memory_reserved = _shim_mem_res


def xpu_device():
    """Return torch.device('xpu:0'); raises if XPU runtime is unavailable."""
    assert torch.xpu.is_available(), (
        "XPU runtime not available — install torch with the +xpu wheel "
        "(pip install torch --index-url https://download.pytorch.org/whl/xpu)"
    )
    return torch.device("xpu:0")


def xpu_available() -> bool:
    return bool(getattr(torch, "xpu", None)) and torch.xpu.is_available()


def install_select_device_xpu_shim():
    # Consumer modules (validator, predictor, ...) bind select_device at
    # import time via `from ultralytics.utils.torch_utils import select_device`,
    # so patching only torch_utils.select_device leaves stale references. Patch
    # every module that imported it as well.
    import importlib
    from ultralytics.utils import torch_utils as _ut

    _orig = _ut.select_device

    def _select(device="", newline=False, verbose=True):
        if isinstance(device, str) and device.startswith("xpu"):
            return torch.device(device)
        if isinstance(device, torch.device) and device.type == "xpu":
            return device
        return _orig(device, newline, verbose)

    _ut.select_device = _select

    _consumers = (
        "ultralytics.engine.validator",
        "ultralytics.engine.predictor",
        "ultralytics.engine.exporter",
        "ultralytics.engine.trainer",
        "ultralytics.utils.benchmarks",
        "ultralytics.utils.checks",
        "ultralytics.models.sam.predict",
        "ultralytics.models.yolo.yoloe.val",
        "ultralytics.solutions.similarity_search",
    )
    for _name in _consumers:
        try:
            _mod = importlib.import_module(_name)
        except Exception:
            continue
        if getattr(_mod, "select_device", None) is not None:
            _mod.select_device = _select
