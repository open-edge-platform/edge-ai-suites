from typing import Dict, List, Optional, Protocol, runtime_checkable

from fastapi import APIRouter


@runtime_checkable
class FeatureModule(Protocol):
    id: str
    requires: List[str]      # capability names
    router: APIRouter

    # Attached by registry.register() from utils/pipeline_catalog.py.
    label: str
    depends_on: List[str]    # feature ids
    stage: Optional[str]     # the pipeline stage this feature owns, if any

    def build(self) -> None: ...

    def teardown(self) -> None: ...

    def ui_descriptor(self) -> Dict: ...
