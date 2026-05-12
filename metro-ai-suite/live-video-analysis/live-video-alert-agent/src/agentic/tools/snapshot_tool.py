# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
capture_snapshot tool — writes the latest frame from a stream to disk.

Configuration (environment variables):
    SNAPSHOT_DIR — base directory for snapshot files (default: ``snapshots/``)

File naming:  {SNAPSHOT_DIR}/{stream_id}/{alert_name}_{timestamp}.jpg
"""

import asyncio
import logging
import os
import time
from typing import Optional

import cv2

from src.config import settings

logger = logging.getLogger(__name__)

# Registry: stream_id → frame retrieval callback (injected by AgentManager)
# Signature: (stream_id: str) -> Optional[np.ndarray]
_frame_callbacks: dict = {}


def register_frame_callback(stream_id: str, callback):
    """Called by AgentManager to register per-stream frame accessors."""
    _frame_callbacks[stream_id] = callback


def unregister_frame_callback(stream_id: str):
    _frame_callbacks.pop(stream_id, None)


async def capture_snapshot(
    stream_id: str,
    alert_name: str = "alert",
    frame=None,
) -> dict:
    """Save a frame as a JPEG snapshot to disk.

    If *frame* is provided it is used directly (pinned-frame mode).
    Otherwise the latest frame is fetched via the registered callback.
    """
    if frame is None:
        callback = _frame_callbacks.get(stream_id)
        if callback is None:
            logger.warning(f"capture_snapshot: no frame callback for stream '{stream_id}'")
            return {"status": "skipped", "reason": "no frame callback registered"}

        try:
            frame = callback(stream_id)
        except Exception as exc:
            logger.error(f"capture_snapshot: frame callback error: {exc}")
            return {"status": "error", "reason": str(exc)}

    if frame is None:
        return {"status": "skipped", "reason": "no frame available"}

    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_alert = alert_name.replace(" ", "_").replace("/", "_")
    safe_stream = stream_id.replace("/", "_").replace(":", "_")
    out_dir = os.path.join(settings.SNAPSHOT_DIR, safe_stream)
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{safe_alert}_{ts}.jpg"
    path = os.path.join(out_dir, filename)

    def _write() -> bool:
        return cv2.imwrite(path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    success = await asyncio.to_thread(_write)
    if not success:
        logger.error(f"cv2.imwrite failed — check path permissions or codec: {path}")
        return {"status": "error", "reason": f"cv2.imwrite returned False for path: {path}"}

    logger.info(f"Snapshot saved: {path}")
    return {"status": "saved", "path": path}
