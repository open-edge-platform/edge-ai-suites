import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from dto.summarizer_dto import SummaryRequest
from pipeline import Pipeline
from utils.config_loader import config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/mindmap")
async def generate_mindmap(request: SummaryRequest):
    pipeline = Pipeline(request.session_id)
    try:
        mindmap_text = pipeline.run_mindmap()
        logger.info("Mindmap generated successfully.")
        return {"mindmap": mindmap_text, "error": ""}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error during mindmap generation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Mindmap generation failed: {e}"
        )


class MindmapFeature:
    id: str = "mindmap"
    requires: List[str] = ["text_gen"]
    depends_on: List[str] = ["summary"]
    router: APIRouter = router

    def __init__(self) -> None:
        self.system_prompt = None

    def build(self) -> None:
        mindmap_cfg = getattr(config, "mindmap", None)
        self.system_prompt = getattr(mindmap_cfg, "system_prompt", None)
        logger.info("MindmapFeature built.")

    def teardown(self) -> None:
        self.system_prompt = None
        logger.info("MindmapFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "endpoints": {
                "mindmap": "/mindmap",
            },
        }
