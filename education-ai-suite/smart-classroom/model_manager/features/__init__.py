from .protocols import FeatureModule
from .registry import REGISTRY, in_dependency_order, register
from .resolver import EffectiveFeatures, resolve

__all__ = [
    "EffectiveFeatures",
    "FeatureModule",
    "REGISTRY",
    "in_dependency_order",
    "register",
    "register_builtin_features",
    "resolve",
]


def register_builtin_features() -> None:
    # Imported lazily: the feature modules pull in FastAPI/pipeline deps that
    # should not be required merely to import the features package.
    from .builtins import register_builtin_features as _register
    _register()
