"""Board (content-screen) OCR service helpers.

Low-level readers for the board OCR extraction, shared by the HTTP API
(``api.board_ocr``) and the audio-summary pipeline (``summarizer_component``):
  * read_board_ocr()           - raw board OCR extraction + status for a session
                                 (produced by BoardOCRWorker -> board_ocr.txt)
  * read_board_ocr_text_only() - the combined board text, normalized to one line
                                 per frame (used by the summarizer pipeline)
"""
import json
import os
import logging
from typing import Optional

from fastapi import HTTPException
from utils.runtime_config_loader import RuntimeConfig

logger = logging.getLogger(__name__)


def _board_ocr_path(session_id: str) -> str:
    project_config = RuntimeConfig.get_section("Project")
    return os.path.join(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
        "board_ocr",
        "board_ocr.txt",
    )


def read_board_ocr(session_id: Optional[str]) -> dict:
    """Return the board OCR extraction + processing status for a session.

    Resolution order for `session_id`:
      1. Explicit argument (header/query)
      2. The board OCR controller's currently active session

    Returns {session_id, status, count, results[], text}. `status` is one of:
      - "done"                         (all frames extracted and OCR'd)
      - "ocr_in_progress"              (extraction finished, OCR worker draining)
      - "frame_extraction_in_progress" (still extracting frames from the source)
      - "not_started"                  (nothing running, no file)
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

    ocr_path = _board_ocr_path(session_id)
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


def _normalize_board_text(raw: str) -> str:
    """Flatten the newline-heavy per-frame OCR text into one readable line per slide/frame.

    board_ocr.txt records join their recognized lines with '\\n' and frames are joined with
    '\\n\\n'; feeding that raw shred of newlines makes downstream LLMs emit fragmented
    keywords. Collapse intra-frame lines to spaces and keep one frame per line so consumers
    see coherent slide-level text.
    """
    if not raw:
        return ""
    frames = [f for f in raw.split("\n\n") if f.strip()]
    slides = []
    for frame in frames:
        lines = [ln.strip() for ln in frame.splitlines() if ln.strip()]
        if lines:
            slides.append(" ".join(lines))
    return "\n".join(slides)


def read_board_ocr_text_only(session_id: Optional[str]) -> str:
    """Return the combined board OCR text for a session, normalized to one line per frame,
    or "" if none is available. Non-raising."""
    try:
        board = read_board_ocr(session_id)
    except HTTPException:
        return ""
    return _normalize_board_text(board.get("text") or "")
