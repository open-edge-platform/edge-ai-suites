import logging
from dataclasses import dataclass
from typing import Mapping, Optional, Set

from utils.pipeline_catalog import topo_sort

from .registry import REGISTRY

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectiveFeatures:
    features: frozenset[str]
    capabilities: frozenset[str]

    def is_enabled(self, fid: str) -> bool:
        return fid in self.features

    def needs_capability(self, cap: str) -> bool:
        return cap in self.capabilities


def resolve(raw_flags: Optional[Mapping[str, bool]]) -> EffectiveFeatures:
    if raw_flags is None:
        enabled: Set[str] = set(REGISTRY)
        logger.info(
            "No 'features:' config block found; enabling all %d registered "
            "features (backward compatibility).",
            len(enabled),
        )
    else:
        enabled = {fid for fid, on in raw_flags.items() if on}
        unknown = sorted(enabled - set(REGISTRY))
        if unknown:
            raise ValueError(f"Unknown feature id: {unknown[0]!r}")

    # Validates the whole graph, not just the part the enabled features reach,
    # so a cycle is reported at startup rather than when someone enables it.
    topo_sort(list(REGISTRY), lambda fid: REGISTRY[fid].depends_on, "feature id")

    _close_over_dependencies(enabled)

    capabilities: Set[str] = set()
    for fid in enabled:
        capabilities.update(REGISTRY[fid].requires)

    return EffectiveFeatures(
        features=frozenset(enabled),
        capabilities=frozenset(capabilities),
    )


def _close_over_dependencies(enabled: Set[str]) -> None:
    """Grow `enabled` until it holds everything the live features need.

    So a feature switched off in config.yaml still runs if something enabled
    needs it. config-schema.cjs warns about that, off the same graph.
    """
    pending = list(enabled)
    while pending:
        fid = pending.pop()
        for dep in REGISTRY[fid].depends_on:
            if dep in enabled:
                continue
            enabled.add(dep)
            pending.append(dep)
            logger.info("Auto-enabling feature %r (required by %r).", dep, fid)
