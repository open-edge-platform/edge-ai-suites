import logging
import os
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from dto.summarizer_dto import SummaryRequest
from pipeline import Pipeline
from utils.locks import audio_pipeline_lock
from utils.runtime_config_loader import RuntimeConfig
from utils.scp_sender import get_scp_sender
from utils.session_state_manager import SessionState
from utils.telegram_sender import get_sender

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/content-segmentation")
def content_segmentation(request: SummaryRequest):

    if audio_pipeline_lock.locked():
        raise HTTPException(status_code=429, detail="Session Active, Try Later")

    pipeline = Pipeline(request.session_id)

    session_state = SessionState.get_session_state(request.session_id)
    logger.info(f"📋 Content-segmentation request for session: {request.session_id}")
    logger.info(f"   Session state: {session_state}")

    try:
        contents_json = pipeline.run_content_segmentation()
        logger.info("✅ content segmentation generated successfully.")

        project_config = RuntimeConfig.get_section("Project")
        session_dir = os.path.join(
            project_config.get("location", "outputs"),
            project_config.get("name", "default"),
            request.session_id,
        )
        sender = get_sender()
        if sender:
            sender.send_content_package_async(request.session_id, session_dir)
        scp = get_scp_sender()
        if scp:
            scp.send_content_package_async(request.session_id, session_dir)

        return JSONResponse(content={"session_id": request.session_id})

    except HTTPException as http_exc:
        raise http_exc

    except Exception as e:
        logger.exception(f"❌ Error during content segmentation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"content segmentation failed: {e}"
        )


class SegmentationFeature:

    id: str = "topic_segmentation"
    requires: List[str] = ["text_gen"]
    depends_on: List[str] = ["asr", "content_search"]
    router: APIRouter = router

    def build(self) -> None:
        logger.info("SegmentationFeature built.")

    def teardown(self) -> None:
        logger.info("SegmentationFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "endpoints": {
                "content_segmentation": "/content-segmentation",
            },
        }
