from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from components.board_ocr.feature_base import Capability, FeatureModule
from components.board_ocr.board_ocr_service import read_board_ocr, summarize_board_ocr

board_ocr_router = APIRouter()


@board_ocr_router.get("/board-ocr/ocr")
def get_board_ocr_endpoint(
    x_session_id: Optional[str] = Header(None),
):
    # Task 1 — return the board (content-screen) OCR extraction + status.
    return JSONResponse(
        content=read_board_ocr(x_session_id), status_code=200
    )


@board_ocr_router.post("/board-ocr/summary")
def board_ocr_summary_endpoint(
    x_session_id: Optional[str] = Header(None),
):
    # Task 2 — summarize the board OCR text via VLM/LLM (placeholder).
    return JSONResponse(
        content=summarize_board_ocr(x_session_id), status_code=200
    )


class SummaryWithOcrFeature(FeatureModule):
    id = "summary_with_ocr"
    requires = [Capability.OCR, Capability.TEXT_GEN]
    depends_on = ["summary"]
    router = board_ocr_router

    def build(self) -> None:
        # The board OCR pipeline is owned by the module-level controller in
        # components.board_ocr.board_ocr_pipeline. It runs as a twin of the
        # VA content pipeline: endpoints.py starts it when the content pipeline
        # starts and stops it when the content pipeline stops or reaches EOS.
        # This feature therefore does not own the pipeline lifecycle.
        pass

    def teardown(self) -> None:
        pass

    def ui_descriptor(self) -> dict:
        return {"panel": "board-ocr", "tab": "post-class"}
