"""Board (content-screen) OCR readers, shared by the HTTP API (``api.board_ocr``)
and the audio-summary pipeline (``summarizer_component``).
"""
import json
import os
import logging
from typing import Optional, Tuple

from fastapi import HTTPException
from utils.runtime_config_loader import RuntimeConfig
from utils.session_paths import SessionPaths

logger = logging.getLogger(__name__)


def read_board_ocr(session_id: Optional[str]) -> dict:
    """Raw board OCR extraction for a session, falling back to the controller's
    active session when `session_id` is None.

    Returns {session_id, status, count, results[], text}. `status` is one of
    "done", "ocr_in_progress", "frame_extraction_in_progress", "not_started".
    """
    from components.board_ocr.board_ocr_pipeline import (
        get_active_session_id,
        get_status,
    )

    if not session_id:
        session_id = get_active_session_id()

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "No board OCR session available. Provide x-session-id header, "
                "or enable board_ocr in config.yaml with a source."
            ),
        )

    status = get_status(session_id)

    if status == "not_started":
        raise HTTPException(
            status_code=404,
            detail=f"No board OCR result found for session {session_id}",
        )

    ocr_path = str(SessionPaths.board_ocr_dir(session_id) / "board_ocr.txt")
    results = []
    if os.path.exists(ocr_path):
        try:
            with open(ocr_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Skipping malformed board OCR line in {ocr_path}"
                        )
        except Exception as e:
            logger.error(f"Error reading board OCR result: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    combined_text = "\n\n".join(r.get("text", "") for r in results if r.get("text"))
    return {
        "session_id": session_id,
        "status": status,
        "count": len(results),
        "results": results,
        "text": combined_text,
    }


def combined_board_text(board: dict) -> str:
    """Board text from a read_board_ocr() result, ready for an LLM prompt:
    deduped, then flattened to one line per frame.

    Dedup runs even when the status is "done": the status flips as soon as the
    frame backlog drains, a moment before the worker's finalize pass rewrites
    the file, so a "done" read can still see raw records. ``clean_records`` is
    idempotent and leaves the file untouched, so this is always safe.
    """
    from components.board_ocr.board_ocr_pipeline import clean_records

    records = clean_records(board.get("results") or [])
    if board.get("status") != "done":
        logger.info(
            f"Board OCR still {board.get('status')} for session {board.get('session_id')}; "
            f"cleaned {board.get('count')} -> {len(records)} records in memory "
            f"(summary may not cover the whole session)"
        )

    slides = []
    for rec in records:
        lines = [ln.strip() for ln in (rec.get("text") or "").splitlines() if ln.strip()]
        if lines:
            slides.append(" ".join(lines))
    return "\n".join(slides)


def read_board_ocr_with_status(session_id: Optional[str]) -> Tuple[str, str]:
    """(board_text, status) for a session; ("", "not_started") if unavailable.

    Non-raising. Callers running alongside the pipeline use the status to warn
    that their board section only covers what has been OCR'd so far.
    """
    try:
        board = read_board_ocr(session_id)
    except HTTPException:
        return "", "not_started"
    return combined_board_text(board), board.get("status", "not_started")
