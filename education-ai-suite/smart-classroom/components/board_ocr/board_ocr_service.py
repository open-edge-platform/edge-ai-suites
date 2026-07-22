"""Board (content-screen) OCR service helpers.

Two responsibilities, both exposed under the /board-ocr/* router:
  * read_board_ocr()      - return the raw board OCR extraction for a session
                            (task 1; produced by BoardOCRWorker -> board_ocr.txt)
  * summarize_board_ocr() - summarize that OCR text via VLM/LLM (task 2)

The summarization is a PLACEHOLDER: the VLM/LLM capability is still being
reworked, so the actual model call is not wired yet. Per the modular design
(doc 6.2/6.4), the summary feature requires the `text_gen` capability and should
acquire it from ModelManager.instance().text_gen() once the Hub lands.
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


def summarize_board_ocr(session_id: Optional[str]) -> dict:
    """Summarize the board OCR text via VLM/LLM.

    PLACEHOLDER — the VLM/LLM module is still being updated, so the model call is
    not wired yet; this returns the assembled board text stats and a pending
    status so the API/data flow can be exercised end to end.

    When the Hub lands, replace the TODO below with a real summarization call:
        tg = ModelManager.instance().text_gen()
        prompt = _build_board_summary_prompt(board["text"])
        summary = "".join(tg.generate(prompt, stream=True))
    """
    board = read_board_ocr(session_id)  # 400/404 if missing

    # TODO(VLM/LLM): call the text_gen / VLM capability to produce the summary.
    summary = None
    logger.info(
        f"Board OCR summary requested for session {board['session_id']} "
        f"({board['count']} frames, {len(board['text'])} chars) — "
        f"VLM/LLM not wired yet, returning placeholder"
    )

    return {
        "session_id": board["session_id"],
        "status": "pending_vlm_integration",
        "board_ocr_status": board["status"],
        "frames": board["count"],
        "board_text_chars": len(board["text"]),
        "summary": summary,
    }
