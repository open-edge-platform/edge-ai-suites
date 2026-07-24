import logging
from typing import Dict, List

from fastapi import APIRouter

from utils.config_loader import config

logger = logging.getLogger(__name__)

router = APIRouter()


class QAFeature:

    id: str = "qa"
    requires: List[str] = ["text_gen"]
    depends_on: List[str] = ["content_search"]
    router: APIRouter = router

    def __init__(self) -> None:
        self.settings = None

    def build(self) -> None:
        """Read the Q&A feature config."""
        cs = getattr(config, "content_search", None)
        self.settings = getattr(cs, "qa", None)
        logger.info("QAFeature built.")

    def teardown(self) -> None:
        self.settings = None
        logger.info("QAFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
        }
