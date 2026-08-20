# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import json
import logging
import re
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
from utils.markdown_cleaner import strip_think_tokens

logger = logging.getLogger(__name__)

router = APIRouter()

# smart-classroom root: api/vlm_chat.py -> parents[1]
_SC_ROOT = Path(__file__).resolve().parents[1]
_CONTENT_SEARCH_DIR = _SC_ROOT / "content_search"

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([^>\n]+)>\s*(.*?)</function>\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)
_TOOL_PARAMETER_RE = re.compile(
    r"<parameter=([^>\n]+)>\s*(.*?)\s*</parameter>",
    re.DOTALL | re.IGNORECASE,
)


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


def _selected_tools(chat_req) -> Optional[List[dict]]:
    tools = chat_req.tools
    choice = chat_req.tool_choice
    if not tools or choice == "none":
        return None
    if not isinstance(choice, dict):
        return tools

    function = choice.get("function") or {}
    name = function.get("name")
    if not name:
        return tools
    selected = [
        tool for tool in tools
        if (tool.get("function") or {}).get("name") == name
    ]
    if not selected:
        raise ValueError(f"tool_choice references unknown function: {name}")
    return selected


def _render_chat_prompt(chat_req, handler, tools: List[dict]) -> str:
    messages = [message.model_dump(exclude_none=True) for message in chat_req.messages]
    return handler.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
        tools=tools,
    )


def _parse_tool_response(output: str) -> tuple[Optional[str], List[dict]]:
    if "</think>" in output and "<think>" not in output:
        output = output.split("</think>", 1)[1]
    cleaned = strip_think_tokens(output)
    tool_calls = []
    for match in _TOOL_CALL_RE.finditer(cleaned):
        arguments = {
            parameter.group(1).strip(): parameter.group(2).strip()
            for parameter in _TOOL_PARAMETER_RE.finditer(match.group(2))
        }
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex}",
            "type": "function",
            "function": {
                "name": match.group(1).strip(),
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        })

    content = _TOOL_CALL_RE.sub("", cleaned).strip() or None
    return content, tool_calls


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
            enable_thinking=chat_req.enable_thinking,
        )
        return StreamingResponse(
            _sse_stream(token_iter, model_name),
            media_type="text/event-stream",
        )

    generation_prompt = prompt
    generation_kwargs = {
        "images": image_tensors,
        "stream": False,
        "max_new_tokens": chat_req.max_completion_tokens,
        "temperature": chat_req.temperature,
    }
    try:
        tools = _selected_tools(chat_req)
        if tools:
            generation_prompt = _render_chat_prompt(chat_req, handler, tools)
    except Exception as exc:  # noqa: BLE001 - tokenizer template validation
        return JSONResponse(
            status_code=400, content={"error": f"Invalid tools: {exc}"}
        )

    if tools:
        generation_kwargs["pre_templated"] = True
    else:
        generation_kwargs["enable_thinking"] = chat_req.enable_thinking

    output = await run_in_threadpool(
        handler.generate,
        generation_prompt,
        **generation_kwargs,
    )
    content, tool_calls = (
        _parse_tool_response(str(output))
        if tools
        else (str(output), [])
    )
    finish_reason = "tool_calls" if tool_calls else "stop"
    message = mods.ChatCompletionDelta(
        role="assistant", content=content, tool_calls=tool_calls or None
    )

    response = mods.ChatCompletionResponse(
        id=str(uuid.uuid4()),
        object="chat.completion",
        created=int(time.time()),
        model=model_name,
        choices=[
            mods.ChatCompletionChoice(
                index=0,
                message=message,
                finish_reason=finish_reason,
            )
        ],
    )
    return JSONResponse(content=response.model_dump())
