import logging
from types import SimpleNamespace
from typing import Dict, Optional

from fastapi import FastAPI

from model_manager import ModelManager
from model_manager.features import (
    in_dependency_order,
    register_builtin_features,
    resolve,
)
from utils.config_loader import config

logger = logging.getLogger(__name__)


def _feature_flags(cfg) -> Optional[Dict[str, bool]]:
    features = getattr(cfg, "features", None)
    if features is None:
        return None
    flags: Dict[str, bool] = {}
    for fid, spec in vars(features).items():
        if isinstance(spec, bool):
            flags[fid] = spec
        elif isinstance(spec, SimpleNamespace):
            flags[fid] = bool(getattr(spec, "enabled", True))
        else:
            flags[fid] = bool(spec)
    return flags


NO_FEATURES_MESSAGE = (
    "No features are enabled. Enable at least one feature in the "
    "'features:' block of config.yaml"
)


def resolve_effective_features():
    """Register built-ins and resolve the effective feature set from config."""
    register_builtin_features()
    return resolve(_feature_flags(config))


def startup(app: FastAPI) -> None:
    eff = resolve_effective_features()
    logger.info("Enabled features: %s", sorted(eff.features))
    logger.info("Required capabilities: %s", sorted(eff.capabilities))

    if not eff.features:
        raise RuntimeError(NO_FEATURES_MESSAGE)

    app.state.features = eff

    ModelManager.instance().warmup(list(eff.capabilities))

    if eff.is_enabled("video_analytics"):
        from components.va.media_service import ensure_media_service_running
        ensure_media_service_running()  # health-polled, idempotent
        logger.info("MediaMTX ensured running for video_analytics.")

    if eff.is_enabled("content_search"):
        logger.info("content_search enabled; will start via feature build().")

    for feature in in_dependency_order():
        if not eff.is_enabled(feature.id):
            continue
        logger.info("Building feature '%s'...", feature.id)
        feature.build()
        app.include_router(feature.router)
        logger.info("Feature '%s' built and router mounted.", feature.id)

    logger.info("Startup orchestration complete.")