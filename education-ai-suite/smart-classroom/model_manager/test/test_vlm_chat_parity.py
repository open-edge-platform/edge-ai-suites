# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
from unittest import SkipTest
from urllib import request as _request
from urllib.error import URLError


_BASE_URL = os.getenv("SC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
_MODEL = os.getenv("SC_GOLDEN_MODEL", "Qwen/Qwen3-VL-8B-Instruct")


def _require_server() -> None:
    """Skip the test unless the main app /health is reachable and text_gen is up."""
    try:
        with _request.urlopen(f"{_BASE_URL}/health", timeout=3) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, ValueError) as exc:
        raise SkipTest(f"main app not reachable at {_BASE_URL}: {exc}")

    text_gen = (body.get("hub") or {}).get("text_gen") or {}
    if not (text_gen.get("loaded") or text_gen.get("state") == "ready"):
        raise SkipTest(f"text_gen not ready at {_BASE_URL}: {text_gen}")


def _post_chat(prompt: str, *, stream: bool):
    payload = json.dumps({
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
    }).encode("utf-8")
    req = _request.Request(
        f"{_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _request.urlopen(req, timeout=120)


def test_health_reports_text_gen_ready():
    """The gate content-search waits on: /health surfaces a ready text_gen."""
    _require_server()
    with _request.urlopen(f"{_BASE_URL}/health", timeout=3) as resp:
        assert resp.status < 400
        body = json.loads(resp.read().decode("utf-8"))
    assert body.get("status") == "ok"
    text_gen = body["hub"]["text_gen"]
    assert text_gen["loaded"] is True or text_gen["state"] == "ready"


def test_chat_completions_nonstreaming_wire_shape():
    """Non-streaming response matches the OpenAI schema QAService/video_preprocess read."""
    _require_server()
    with _post_chat("Reply with the single word: ok", stream=False) as resp:
        assert resp.status < 400
        data = json.loads(resp.read().decode("utf-8"))

    # Exact keys/types the retired :9900 server produced and clients depend on.
    assert data["object"] == "chat.completion"
    assert isinstance(data["id"], str) and data["id"]
    assert isinstance(data["created"], int)
    assert isinstance(data["model"], str) and data["model"]
    assert isinstance(data["choices"], list) and len(data["choices"]) == 1

    choice = data["choices"][0]
    assert choice["index"] == 0
    assert choice["finish_reason"] == "stop"
    message = choice["message"]
    assert message["role"] == "assistant"
    # This is the exact field the content-search clients extract.
    content = message["content"]
    assert isinstance(content, str) and content.strip()

    golden_prompt = os.getenv("SC_GOLDEN_PROMPT")
    golden_text = os.getenv("SC_GOLDEN_TEXT")
    if golden_prompt and golden_text:
        with _post_chat(golden_prompt, stream=False) as resp:
            g = json.loads(resp.read().decode("utf-8"))
        assert g["choices"][0]["message"]["content"] == golden_text


def test_chat_completions_streaming_sse_shape():
    """Streaming response emits OpenAI chat.completion.chunk SSE, terminated by [DONE]."""
    _require_server()
    roles = []
    content = []
    saw_done = False
    saw_stop = False

    with _post_chat("Reply with the single word: ok", stream=True) as resp:
        assert resp.status < 400
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            body = line[len("data:"):].strip()
            if body == "[DONE]":
                saw_done = True
                break
            chunk = json.loads(body)
            assert chunk["object"] == "chat.completion.chunk"
            delta = chunk["choices"][0]["delta"]
            if "role" in delta:
                roles.append(delta["role"])
            if delta.get("content"):
                content.append(delta["content"])
            if chunk["choices"][0].get("finish_reason") == "stop":
                saw_stop = True

    assert saw_done, "stream did not terminate with [DONE]"
    assert saw_stop, "stream never reported finish_reason=stop"
    assert roles and roles[0] == "assistant"
    assert "".join(content).strip()


if __name__ == "__main__":
    _names = sorted(n for n in dir() if n.startswith("test_"))
    _passed = _skipped = 0
    _failed = []
    for _n in _names:
        try:
            globals()[_n]()
            _passed += 1
            print(f"PASS {_n}")
        except SkipTest as _s:
            _skipped += 1
            print(f"SKIP {_n}: {_s}")
        except Exception as _e:  # noqa: BLE001 - test harness
            _failed.append(_n)
            print(f"FAIL {_n}: {_e!r}")
    print(f"\n{_passed} passed, {_skipped} skipped, {len(_failed)} failed")
    raise SystemExit(1 if _failed else 0)
