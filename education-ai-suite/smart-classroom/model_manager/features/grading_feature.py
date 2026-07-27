# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class GradingFeature:
    """
    Grading feature integration.
    
    The grading service runs as a separate microservice (port 9012) with its own
    API routes. This feature acts as a registration point so the UI knows grading
    is available and can route requests to the grading backend via the proxy.
    """

    id: str = "grading"
    requires: List[str] = []
    depends_on: List[str] = []
    router = None  # Grading has its own separate API service

    def build(self) -> None:
        logger.info("GradingFeature registered (separate microservice).")

    def teardown(self) -> None:
        logger.info("GradingFeature torn down.")

    def ui_descriptor(self) -> Dict:
        """
        Return UI configuration for the grading feature.
        
        The UI proxies /grading-api to the separate grading service (port 9012).
        All grading endpoints are prefixed with /grading-api in the frontend.
        """
        return {
            "id": self.id,
            "type": "microservice",
            "endpoints": {
                "health": "/grading-api/health",
                "config": "/grading-api/grading/config",
                "rubrics": "/grading-api/rubrics",
                "upload_rubric": "/grading-api/rubrics/upload",
                "tasks": "/grading-api/grading/tasks",
                "task_detail": "/grading-api/grading/tasks/{task_id}",
                "task_summary": "/grading-api/grading/tasks/{task_id}/summary",
                "task_log": "/grading-api/grading/tasks/{task_id}/log",
                "fs_list": "/grading-api/fs/list",
            },
        }
