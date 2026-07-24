import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from dto.summarizer_dto import SummaryRequest
from pipeline import Pipeline
from utils.config_loader import config
from utils.locks import audio_pipeline_lock

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/summarize")
async def summarize_audio(request: SummaryRequest):
    if audio_pipeline_lock.locked():
        raise HTTPException(status_code=429, detail="Session Active, Try Later")

    pipeline = Pipeline(request.session_id)

    async def event_stream():
        for token in pipeline.run_summarizer():
            if token.startswith("[ERROR]:"):
                logger.error(f"Error while summarizing: {token}")
                yield json.dumps({"token": "", "error": token}) + "\n"
                break
            else:
                yield json.dumps({"token": token, "error": ""}) + "\n"
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
        self.system_prompt = None

    def build(self) -> None:
        """Read the summary feature config (mode, system_prompt)."""
        summarizer_cfg = config.models.summarizer
        self.mode = getattr(summarizer_cfg, "mode", None)
        self.system_prompt = getattr(summarizer_cfg, "system_prompt", None)
        logger.info("SummaryFeature built; mode=%s.", self.mode)

    def teardown(self) -> None:
        self.mode = None
        self.system_prompt = None
        logger.info("SummaryFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "endpoints": {
                "summarize": "/summarize",
            },
        }
