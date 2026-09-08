import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from dto.summarizer_dto import SummaryRequest
from pipeline import Pipeline
from utils.config_loader import config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/summarize")
async def summarize_audio(request: SummaryRequest):
    pipeline = Pipeline(request.session_id)

    async def event_stream():
        warned_partial_board = False
        for item in pipeline.run_summarizer():
            # A segmented summary yields progress dicts before any token.
            if isinstance(item, dict):
                yield json.dumps({"token": "", "error": "", **item}) + "\n"
                await asyncio.sleep(0)
                continue
            if not warned_partial_board and pipeline.board_ocr_partial:
                warned_partial_board = True
                yield json.dumps(
                    {"token": "", "error": "", "board_ocr_partial": True}
                ) + "\n"
            if item.startswith("[ERROR]:"):
                logger.error(f"Error while summarizing: {item}")
                yield json.dumps({"token": "", "error": item}) + "\n"
                break
            else:
                yield json.dumps({"token": item, "error": ""}) + "\n"
            await asyncio.sleep(0)

    return StreamingResponse(event_stream(), media_type="application/json")


class SummaryFeature:
    """F2 transcript summarization exposed as a FeatureModule."""

    id: str = "summary"
    requires: List[str] = ["text_gen"]
    depends_on: List[str] = ["asr"]
    router: APIRouter = router

    def __init__(self) -> None:
        self.mode = None

    def build(self) -> None:
        """Read the summary feature config (mode)."""
        summarizer_cfg = config.models.summarizer
        self.mode = getattr(summarizer_cfg, "mode", None)
        logger.info("SummaryFeature built; mode=%s.", self.mode)

    def teardown(self) -> None:
        self.mode = None
        logger.info("SummaryFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "endpoints": {
                "summarize": "/summarize",
            },
        }
