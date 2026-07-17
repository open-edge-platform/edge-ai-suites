"""TODO: PLACEHOLDER for minimal Feature Module contract (design doc section 6.4).
"""
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter


class Capability(str, Enum):
    """Hub-owned capabilities a feature can require (doc section 5.1)."""

    OCR = "ocr"
    TEXT_GEN = "text_gen"
    ASR = "asr"


class FeatureModule:
    """Base class for a self-describing feature (doc section 6.4).

    Subclasses declare `id`, `requires`, `depends_on`, and `router` at import
    time (side-effect-free), and construct runtime objects only in `build()`.
    """

    id: str = ""
    requires: List[Capability] = []
    depends_on: List[str] = []
    router: Optional[APIRouter] = None

    def build(self) -> None:
        """Construct runtime objects — called by the orchestrator only if enabled."""

    def teardown(self) -> None:
        """Release whatever build() created (mirror of build())."""

    def ui_descriptor(self) -> dict:
        """Panel(s) the SPA should render for this feature."""
        return {}
