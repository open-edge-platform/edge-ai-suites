# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, List, Optional

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from model_manager import ModelManager

logger = logging.getLogger(__name__)

router = APIRouter()

# smart-classroom root: api/vlm_chat.py -> parents[1]
_SC_ROOT = Path(__file__).resolve().parents[1]
_CONTENT_SEARCH_DIR = _SC_ROOT / "content_search"


def _import_vlm_serving() -> SimpleNamespace:

    if str(_CONTENT_SEARCH_DIR) not in sys.path:
        sys.path.append(str(_CONTENT_SEARCH_DIR))
    from components.vlm.vlm_openvino_serving.utils.data_models import (  # noqa: E402
        ChatCompletionChoice,
        ChatCompletionDelta,
        ChatCompletionResponse,
        ChatRequest,
        MessageContentImageUrl,
        MessageContentText,
    )
    from components.vlm.vlm_openvino_serving.utils.utils import load_images  # noqa: E402

    return SimpleNamespace(
        ChatRequest=ChatRequest,
        ChatCompletionResponse=ChatCompletionResponse,
        ChatCompletionChoice=ChatCompletionChoice,
        ChatCompletionDelta=ChatCompletionDelta,
        MessageContentText=MessageContentText,
        MessageContentImageUrl=MessageContentImageUrl,
        load_images=load_images,
    )


def _extract_prompt_and_images(messages, mods: SimpleNamespace):
    last_user_message = next(
        (m for m in reversed(messages) if m.role == "user"), None
    )
    image_urls: List[str] = []
    prompt: Optional[str] = None
    if last_user_message is not None:
        if isinstance(last_user_message.content, str):
            prompt = last_user_message.content
        else:
            for content in last_user_message.content:
                if isinstance(content, mods.MessageContentImageUrl):
                    url = content.image_url.get("url")
                    if url:
                        image_urls.append(url)
                elif isinstance(content, mods.MessageContentText):
                    prompt = content.text
                elif isinstance(content, str):
                    prompt = content
    return prompt, image_urls


def _model_name(requested: Optional[str]) -> str:
    try:
        from utils.config_loader import config

        name = getattr(getattr(config.models, "text_gen", None), "vlm_name", None)
        if name:
            return str(name)
    except Exception:  
        pass
    return requested or "text_gen"


def _sse_stream(token_iter: Iterator[str], model_name: str) -> Iterator[str]:
    created = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    def _chunk(delta: dict, finish_reason: Optional[str] = None) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [
                {"index": 0, "delta": delta, "finish_reason": finish_reason}
            ],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # First chunk announces the assistant role (OpenAI convention).
    yield _chunk({"role": "assistant"})
    for token in token_iter:
        if token:
            yield _chunk({"content": token})
    yield _chunk({}, finish_reason="stop")
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completion backed by the warm in-process VLM."""
    mods = _import_vlm_serving()

    try:
        body = await request.json()
        chat_req = mods.ChatRequest(**body)
    except Exception as exc:  # noqa: BLE001 - malformed body / schema violation
        return JSONResponse(
            status_code=400, content={"error": f"Invalid request: {exc}"}
        )

    prompt, image_urls = _extract_prompt_and_images(chat_req.messages, mods)
    if not prompt or not prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Prompt is required"})

    image_tensors = None
    if image_urls:
        try:
            _, image_tensors = await mods.load_images(image_urls)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

    model_name = _model_name(chat_req.model)
    handler = ModelManager.instance().text_gen()

    if chat_req.stream:
        token_iter = handler.generate(
            prompt,
            images=image_tensors,
            stream=True,
            max_new_tokens=chat_req.max_completion_tokens,
            temperature=chat_req.temperature,
        )
        return StreamingResponse(
            _sse_stream(token_iter, model_name),
            media_type="text/event-stream",
        )

    output = await run_in_threadpool(
        handler.generate,
        prompt,
        images=image_tensors,
        stream=False,
        max_new_tokens=chat_req.max_completion_tokens,
        temperature=chat_req.temperature,
    )
    response = mods.ChatCompletionResponse(
        id=str(uuid.uuid4()),
        object="chat.completion",
        created=int(time.time()),
        model=model_name,
        choices=[
            mods.ChatCompletionChoice(
                index=0,
                message=mods.ChatCompletionDelta(role="assistant", content=str(output)),
                finish_reason="stop",
            )
        ],
    )
    return JSONResponse(content=response.model_dump())
