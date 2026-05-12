# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
log_alert tool — records an alert event to the application log and the
in-memory history managed by AlertStateManager.

This is always the baseline tool included in every alert's tool list.
It does not require any external service configuration.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def log_alert(
    stream_id: str,
    alert_name: str,
    answer: str,
    reason: str,
    consecutive_count: int = 1,
    escalated: bool = False,
    snapshot_path: Optional[str] = None,
) -> dict:
    """Log an alert detection event. Always executed for every YES detection."""
    level = logging.WARNING if answer == "YES" else logging.DEBUG
    logger.log(
        level,
        f"ALERT {answer} | stream={stream_id} | "
        f"alert={alert_name} | consecutive={consecutive_count} | "
        f"escalated={escalated} | reason={reason!r}"
        + (f" | snapshot={snapshot_path}" if snapshot_path else ""),
    )
    return {
        "status": "logged",
        "stream_id": stream_id,
        "alert_name": alert_name,
        "answer": answer,
        "consecutive_count": consecutive_count,
        "escalated": escalated,
    }
