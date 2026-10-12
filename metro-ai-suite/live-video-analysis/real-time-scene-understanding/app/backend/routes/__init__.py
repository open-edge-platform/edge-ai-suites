from .alert import build_alert_router
from .health import build_health_router
from .registry import build_registry_router
from .runtime import build_runtime_config_router
from .stream import build_stream_router

__all__ = [
    "build_alert_router",
    "build_health_router",
    "build_registry_router",
    "build_runtime_config_router",
    "build_stream_router",
]
