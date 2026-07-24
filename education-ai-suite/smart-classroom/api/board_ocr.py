# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from components.board_ocr.board_ocr_service import (
    _normalize_board_text,
    read_board_ocr,
)
from utils.config_loader import config
from utils.markdown_cleaner import strip_think_tokens

logger = logging.getLogger(__name__)

board_ocr_router = APIRouter()


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
            "请综合这些内容，直接输出摘要正文，组织为若干条要点。\n\n"
            "规则:\n"
            "- 用完整、通顺的句子说明板书/屏幕上“呈现了/讲解了/说明了/描述了/列举了”哪些内容，"
            "而不是罗列零散的关键词或短语。\n"
            "- 将同一主题的重复帧或相关帧归纳为一句连贯的表述。\n"
            "- 按主题或授课顺序组织为若干条要点，每条都是一个完整句子。\n"
            "- 忽略水印、网站/频道名称等无关噪声；在含义明确时修正明显的 OCR 错误。\n"
            "- 不要输出任何标题或章节名，直接给出要点。\n"
            "- 如果板书内容为空或无法识别，输出“无”。"
        )
    return (
        "You will receive board content: text captured frame by frame by OCR from a "
        "classroom display / interactive flat panel (slide titles, bullet points, tables, "
        "equations), in chronological order. It may contain OCR noise, watermarks, or "
        "site/channel names, and the same title may repeat across many frames.\n\n"
        "Synthesize this content and output the summary body directly as a few bullet "
        "points.\n\n"
        "Rules:\n"
        "- Write complete, fluent sentences describing WHAT the board presented, e.g. "
        "\"Showed ...\", \"Explained ...\", \"Described ...\", \"Listed ...\".\n"
        "- Do NOT output isolated keywords or fragments. Merge repeated/related frames on "
        "the same topic into one coherent statement.\n"
        "- Organize into a few bullet points by topic or teaching sequence; each bullet is a "
        "full sentence.\n"
        "- Ignore watermarks, channel/site names, and other noise; fix obvious OCR errors "
        "when the meaning is clear.\n"
        "- Do NOT output any heading or section title; give the bullet points directly.\n"
        "- If the board content is empty or unreadable, output \"None\"."
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


@board_ocr_router.get("/board-ocr/ocr")
def get_board_ocr_endpoint(x_session_id: Optional[str] = Header(None)):
    """Return the board (content-screen) OCR extraction + status."""
    return JSONResponse(content=read_board_ocr(x_session_id), status_code=200)


@board_ocr_router.post("/board-ocr/summary")
def board_ocr_summary_endpoint(x_session_id: Optional[str] = Header(None)):
    """Summarize the board OCR text via the text_gen (VLM) capability."""
    return JSONResponse(content=summarize_board_ocr(x_session_id), status_code=200)
