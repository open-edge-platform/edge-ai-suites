import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from dto.summarizer_dto import SummaryRequest
from pipeline import Pipeline
from utils.pipeline_catalog import FEATURE_STAGE
from utils.stage_tracker import stage_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/mindmap")
def generate_mindmap(request: SummaryRequest):
    pipeline = Pipeline(request.session_id)
    try:
        with stage_tracker(pipeline.session_id, FEATURE_STAGE["mindmap"]):
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
    # label / depends_on / stage: utils/pipeline_catalog.py
    router: APIRouter = router

    def build(self) -> None:
        logger.info("MindmapFeature built.")

    def teardown(self) -> None:
        logger.info("MindmapFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "endpoints": {
                "mindmap": "/mindmap",
            },
        }
