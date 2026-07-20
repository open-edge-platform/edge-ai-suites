import yaml
from types import SimpleNamespace
import os
import logging

logger = logging.getLogger(__name__)

# Canonical feature ids recognized in the `features:` config block.
KNOWN_FEATURE_IDS = frozenset({
    "asr",
    "summary",
    "mindmap",
    "topic_segmentation",
    "video_analytics",
    "content_search",
    "qa",
    "report",
})

def _dict_to_namespace(d):
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()})
    return d

def _apply_backcompat(data):
    """Normalize legacy config keys to the current structure in place."""
    if not isinstance(data, dict):
        return data
    models = data.get("models")
    return data

def _validate_features(data):
    """Reject unknown feature ids. An absent block enables all features."""
    if not isinstance(data, dict):
        return
    features = data.get("features")
    if features is None:
        return  # absent => all features enabled downstream
    if not isinstance(features, dict):
        raise ValueError(
            "'features:' config block must be a mapping of feature id -> settings."
        )
    unknown = set(features) - KNOWN_FEATURE_IDS
    if unknown:
        raise ValueError(
            "Unknown feature id(s) in 'features:' config block: "
            + ", ".join(sorted(unknown))
            + ". Known features: "
            + ", ".join(sorted(KNOWN_FEATURE_IDS))
            + "."
        )

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data = _apply_backcompat(data)
    _validate_features(data)
    return _dict_to_namespace(data)

config = load_config()

logger.debug("\n📦 CONFIGURATION START\n" + "-" * 40)
logger.debug(yaml.dump(vars(config), sort_keys=False))
logger.debug("\n" + "-" * 40 + "\n📦 CONFIGURATION END\n")
