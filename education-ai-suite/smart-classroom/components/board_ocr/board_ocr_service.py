"""Board (content-screen) OCR service helpers.

Two responsibilities, both exposed under the /board-ocr/* router:
  * read_board_ocr()      - return the raw board OCR extraction for a session
                            (task 1; produced by BoardOCRWorker -> board_ocr.txt)
  * summarize_board_ocr() - summarize that OCR text via the text_gen (VLM)
                            capability from the ModelManager hub (task 2)
"""
import json
import os
import logging
from typing import Optional

from fastapi import HTTPException
from utils.config_loader import config
from utils.markdown_cleaner import strip_think_tokens
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


def _board_summary_system_prompt(lang: str) -> str:
    """Standalone system prompt for summarizing board/screen OCR text.

    Distinct from ``config.models.summarizer.board_ocr_prompt`` (which is phrased
    as an addendum to the audio-transcript summary); this one stands on its own
    for the /board-ocr/summary endpoint.
    """
    if lang == "zh":
        return (
            "你会收到一段板书内容：通过 OCR 从教室显示屏/交互式白板逐帧捕获的文本"
            "（幻灯片标题、要点、表格、公式等），按时间先后排列，可能含有 OCR 噪声、"
            "水印或网站/频道名称，且同一标题可能在多帧中重复出现。\n\n"
            "请综合这些内容，输出有效 Markdown，且仅包含一个章节:\n\n"
            "## 板书/大屏内容\n- ...\n\n"
            "规则:\n"
            "- 用完整、通顺的句子说明板书/屏幕上“呈现了/讲解了/说明了/描述了/列举了”哪些内容，"
            "而不是罗列零散的关键词或短语。\n"
            "- 将同一主题的重复帧或相关帧归纳为一句连贯的表述。\n"
            "- 按主题或授课顺序组织为若干条要点，每条都是一个完整句子。\n"
            "- 忽略水印、网站/频道名称等无关噪声；在含义明确时修正明显的 OCR 错误。\n"
            "- 如果板书内容为空或无法识别，写 \"- 无\"。"
        )
    return (
        "You will receive board content: text captured frame by frame by OCR from a "
        "classroom display / interactive flat panel (slide titles, bullet points, tables, "
        "equations), in chronological order. It may contain OCR noise, watermarks, or "
        "site/channel names, and the same title may repeat across many frames.\n\n"
        "Synthesize this content and output valid Markdown with exactly one section:\n\n"
        "## Board/IFPD Content\n- ...\n\n"
        "Rules:\n"
        "- Write complete, fluent sentences describing WHAT the board presented, e.g. "
        "\"Showed ...\", \"Explained ...\", \"Described ...\", \"Listed ...\".\n"
        "- Do NOT output isolated keywords or fragments. Merge repeated/related frames on "
        "the same topic into one coherent statement.\n"
        "- Organize into a few bullet points by topic or teaching sequence; each bullet is a "
        "full sentence.\n"
        "- Ignore watermarks, channel/site names, and other noise; fix obvious OCR errors "
        "when the meaning is clear.\n"
        "- If the board content is empty or unreadable, write \"- None\"."
    )


def summarize_board_ocr(session_id: Optional[str]) -> dict:
    """Summarize the board OCR text via the text_gen (VLM) capability."""
    from model_manager import ModelManager

    board = read_board_ocr(session_id)
    board_text = _normalize_board_text(board.get("text") or "")

    if not board_text:
        logger.info(
            f"Board OCR summary requested for session {board['session_id']} — "
            f"no board text available, returning empty summary"
        )
        return {
            "session_id": board["session_id"],
            "status": "no_board_text",
            "board_ocr_status": board["status"],
            "frames": board["count"],
            "board_text_chars": 0,
            "summary": None,
        }

    tg = ModelManager.instance().text_gen()

    model_name = str(config.models.text_gen.vlm_name)
    user_content = board_text
    if "qwen3" in model_name.lower() and not user_content.lstrip().startswith("/no_think"):
        user_content = "/no_think\n" + board_text

    messages = [
        {"role": "system", "content": _board_summary_system_prompt(config.app.language)},
        {"role": "user", "content": user_content},
    ]
    prompt = tg.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    raw = tg.generate(prompt, stream=False)
    summary = strip_think_tokens(raw if isinstance(raw, str) else "".join(raw))

    logger.info(
        f"Board OCR summary generated for session {board['session_id']} "
        f"({board['count']} frames, {len(board_text)} chars -> {len(summary)} chars)"
    )

    return {
        "session_id": board["session_id"],
        "status": "done",
        "board_ocr_status": board["status"],
        "frames": board["count"],
        "board_text_chars": len(board_text),
        "summary": summary,
    }
