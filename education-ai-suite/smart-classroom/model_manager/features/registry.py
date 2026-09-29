from typing import Dict, List

from utils.pipeline_catalog import FEATURES, topo_sort

from .protocols import FeatureModule


REGISTRY: Dict[str, FeatureModule] = {}


def register(module: FeatureModule) -> FeatureModule:
    """Add a feature module, taking its place in the graph from the catalog.

    A module declares only its own behaviour; `label`, `depends_on` and `stage`
    are attached here from utils/pipeline_catalog.py.
    """
    spec = FEATURES.get(module.id)
    if spec is None:
        raise ValueError(
            f"Feature {module.id!r} is not in utils/pipeline_catalog.py; add it "
            "there (and re-run Scripts/gen_catalog.py) before registering it."
        )
    module.label = spec.label
    module.depends_on = list(spec.depends_on)
    module.stage = spec.stage
    REGISTRY[module.id] = module
    return module


def in_dependency_order() -> List[FeatureModule]:
    """Registered modules, each one after everything it depends on."""
    order = topo_sort(
        list(REGISTRY),
        lambda fid: REGISTRY[fid].depends_on,
        what="feature dependency",
    )
    return [REGISTRY[fid] for fid in order]
