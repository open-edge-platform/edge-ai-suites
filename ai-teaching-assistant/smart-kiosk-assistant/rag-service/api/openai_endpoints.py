from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from dto.query_dto import ChatCompletionRequest
from pipeline import get_shared_pipeline
from utils.config_loader import config


router = APIRouter()
logger = logging.getLogger(__name__)


def _flatten_message_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


def _extract_prompt(request: ChatCompletionRequest) -> tuple[str, str | None, list[tuple[str, str]]]:
    user_messages = [message for message in request.messages if message.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    # Index of the final user message in the original sequence — everything
    # before it (user/assistant turns only) becomes conversation history.
    last_user_index = max(i for i, m in enumerate(request.messages) if m.role == "user")
    last_user = _flatten_message_content(request.messages[last_user_index].content).strip()

    system_messages = [message for message in request.messages if message.role == "system"]
    system_prompt = _flatten_message_content(system_messages[-1].content).strip() if system_messages else None

    history: list[tuple[str, str]] = []
    for message in request.messages[:last_user_index]:
        if message.role not in ("user", "assistant"):
            continue
        text = _flatten_message_content(message.content).strip()
        if text:
            history.append((message.role, text))

    return last_user, system_prompt or None, history


@router.post("/v1/chat/completions")
def create_chat_completion(request: ChatCompletionRequest):
    pipeline = get_shared_pipeline()
    prompt, system_prompt, history = _extract_prompt(request)
    model_name = config.api.openai_model_name
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    if request.stream:
        def _stream():
            first_event = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(first_event)}\n\n"

            try:
                for token in pipeline.stream_answer(
                    prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    system_prompt=system_prompt,
                    history=history,
                ):
                    event = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:  # noqa: BLE001
                error_event = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "error": {"message": str(exc)},
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            finally:
                final_event = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(_stream(), media_type="text/event-stream")

    result = pipeline.answer_question(
        prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        system_prompt=system_prompt,
        history=history,
    )

    total_ms = (time.time() - created) * 1000
    logger.info(
        "[CHAT] q=%r prompt_chars=%d ans_chars=%d total=%.0fms",
        prompt[:80], len(prompt), len(result.get("answer", "")), total_ms,
    )

    payload = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["answer"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
    }
    return JSONResponse(content=payload, status_code=200)
