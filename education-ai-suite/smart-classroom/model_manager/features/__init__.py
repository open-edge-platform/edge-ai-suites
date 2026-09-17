from utils.pipeline_catalog import CATALOG, FEATURES, FeatureSpec

from .protocols import FeatureModule
from .registry import REGISTRY, in_dependency_order, register
from .resolver import EffectiveFeatures, resolve

__all__ = [
    "CATALOG",
    "EffectiveFeatures",
    "FEATURES",
    "FeatureModule",
    "FeatureSpec",
    "REGISTRY",
    "in_dependency_order",
    "register",
    "register_builtin_features",
    "resolve",
]


def register_builtin_features() -> None:
    from .builtins import register_builtin_features as _register
    _register()
