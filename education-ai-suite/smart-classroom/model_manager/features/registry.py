from typing import Dict, List

from .protocols import FeatureModule


REGISTRY: Dict[str, FeatureModule] = {}


def register(module: FeatureModule) -> FeatureModule:
    REGISTRY[module.id] = module
    return module


def in_dependency_order() -> List[FeatureModule]:
    ordered: List[FeatureModule] = []
    visited: Dict[str, bool] = {}  # feature id -> fully resolved

    def visit(feature_id: str, stack: List[str]) -> None:
        if visited.get(feature_id):
            return
        if feature_id in stack:
            cycle = " -> ".join([*stack, feature_id])
            raise ValueError(f"Dependency cycle detected: {cycle}")
        if feature_id not in REGISTRY:
            raise ValueError(f"Unknown feature dependency: {feature_id!r}")

        module = REGISTRY[feature_id]
        for dep in module.depends_on:
            visit(dep, [*stack, feature_id])

        visited[feature_id] = True
        ordered.append(module)

    for feature_id in REGISTRY:
        visit(feature_id, [])

    return ordered
