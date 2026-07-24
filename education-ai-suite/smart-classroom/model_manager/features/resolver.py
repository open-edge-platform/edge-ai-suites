import logging
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Set

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

    resolved: Set[str] = set()
    for fid in list(enabled):
        _resolve_feature(fid, enabled, resolved, stack=[])

    capabilities: Set[str] = set()
    for fid in enabled:
        capabilities.update(REGISTRY[fid].requires)

    return EffectiveFeatures(
        features=frozenset(enabled),
        capabilities=frozenset(capabilities),
    )


def _resolve_feature(
    fid: str,
    enabled: Set[str],
    resolved: Set[str],
    stack: List[str],
) -> None:
    if fid in resolved:
        return
    if fid in stack:
        cycle = " -> ".join([*stack, fid])
        raise ValueError(f"Dependency cycle detected: {cycle}")
    if fid not in REGISTRY:
        raise ValueError(f"Unknown feature id: {fid!r}")

    for dep in REGISTRY[fid].depends_on:
        if dep not in enabled:
            enabled.add(dep)
            logger.info("Auto-enabling feature %r (required by %r).", dep, fid)
        _resolve_feature(dep, enabled, resolved, [*stack, fid])

    resolved.add(fid)
