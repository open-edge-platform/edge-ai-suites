from typing import Dict, List, Protocol, runtime_checkable

from fastapi import APIRouter


@runtime_checkable
class FeatureModule(Protocol):
    id: str
    requires: List[str]      # capability names
    depends_on: List[str]    # feature ids
    router: APIRouter

    def build(self) -> None: ...

    def teardown(self) -> None: ...

    def ui_descriptor(self) -> Dict: ...
