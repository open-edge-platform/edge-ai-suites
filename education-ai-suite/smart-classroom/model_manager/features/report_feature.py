# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Dict, List

from fastapi import APIRouter

from api.report import router

logger = logging.getLogger(__name__)


class ReportFeature:

    id: str = "report"
    requires: List[str] = ["text_gen"]
    depends_on: List[str] = ["summary", "mindmap", "topic_segmentation"]
    router: APIRouter = router

    def build(self) -> None:
        logger.info("ReportFeature built.")

    def teardown(self) -> None:
        logger.info("ReportFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "endpoints": {
                "generate": "/report/generate",
                "template_fields": "/report/template-fields",
                "get_report": "/report/{session_id}",
                "download": "/report/{session_id}/download",
                "reselect": "/report/{session_id}/reselect",
            },
        }
