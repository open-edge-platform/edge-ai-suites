# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Dict, List

from fastapi import APIRouter

from api.board_ocr import board_ocr_router

logger = logging.getLogger(__name__)


class BoardOCRFeature:
    """Board / content-screen OCR feature module.

    Exposes two endpoints:
      GET  /board-ocr/ocr      — raw OCR results + processing status for a session
      POST /board-ocr/summary  — LLM-generated summary of the captured board text

    Enabling this feature is the only switch: pipeline lifecycle (FrameExtractor
    + BoardOCRWorker) is driven by the VA content pipeline, which calls
    start_board_ocr() when it starts and stop_board_ocr() when it stops or
    reaches EOS. build() warms nothing by itself; teardown() cleans up any
    active pipeline on application shutdown.
    """

    id: str = "board_ocr"
    requires: List[str] = ["ocr", "text_gen"]
    depends_on: List[str] = ["video_analytics"]
    router: APIRouter = board_ocr_router

    def build(self) -> None:
        logger.info(
            "BoardOCRFeature built — pipeline starts alongside VA content source."
        )

    def teardown(self) -> None:
        from components.board_ocr.board_ocr_pipeline import stop_board_ocr

        stop_board_ocr()
        logger.info("BoardOCRFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "endpoints": {
                "ocr": "/board-ocr/ocr",
                "summary": "/board-ocr/summary",
            },
        }
