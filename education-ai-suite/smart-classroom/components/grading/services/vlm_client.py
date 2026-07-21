"""VLM client for full-page grading.

Sends one page image plus the grading prompt to an OpenAI-compatible VLM
endpoint and returns the raw model text together with client-measured timing.
No proxy is used for the (local) VLM service.
"""
from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path
from typing import Any

import requests

# Mirrors the strict-grader system prompt used elsewhere, adapted for a full
# page that may contain multiple questions.
SYSTEM_PROMPT = (
    "You are a strict exam grader. The image is a full exam page that may "
    "contain multiple questions. Identify every question on the page and grade "
    "each one independently. Read the student's handwritten answers; do not "
    "guess steps the student omitted. Be concise. Do NOT skip any question you "
    "can see on the page."
)


def encode_image(path: Path, max_pixels: int | None = None) -> str:
    """Base64 data-URL for an image. If max_pixels is set and the image exceeds
    it, downscale (preserving aspect ratio) before encoding — an upper bound on
    top of section_split's lossless whitespace compression."""
    if max_pixels:
        from io import BytesIO
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            if w * h > max_pixels:
                scale = (max_pixels / (w * h)) ** 0.5
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                               Image.Resampling.LANCZOS)
                buf = BytesIO()
                im.save(buf, format="JPEG", quality=90)
                b64 = base64.b64encode(buf.getvalue()).decode()
                return f"data:image/jpeg;base64,{b64}"
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def build_payload(model: str, image: Path, user_prompt: str,
                  max_tokens: int, temperature: float,
                  max_image_pixels: int | None = None) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": encode_image(image, max_image_pixels)}},
                    {"type": "text", "text": user_prompt},
                ],
            },
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def grade_page(
    url: str,
    model: str,
    image: Path,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.1,
    timeout: int = 600,
    max_image_pixels: int | None = None,
) -> dict[str, Any]:
    """Grade one page/section. Returns a dict with keys:
    ok, answer, elapsed_seconds, finish_reason, prompt_tokens,
    completion_tokens, error.
    Timing is measured client-side and does not depend on any response field.
    max_image_pixels caps the sent image size (downscale only if exceeded).
    """
    payload = build_payload(model, image, user_prompt, max_tokens, temperature,
                            max_image_pixels)

    start = time.perf_counter()
    try:
        resp = requests.post(
            f"{url}/v1/chat/completions",
            json=payload,
            timeout=timeout,
            proxies={"http": None, "https": None},
        )
    except Exception as exc:
        return {
            "ok": False,
            "answer": "",
            "elapsed_seconds": time.perf_counter() - start,
            "error": f"request failed: {exc}",
        }
    elapsed = time.perf_counter() - start

    if resp.status_code != 200:
        return {
            "ok": False,
            "answer": "",
            "elapsed_seconds": elapsed,
            "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
        }

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    answer = choice.get("message", {}).get("content", "")
    usage = data.get("usage", {})
    return {
        "ok": True,
        "answer": answer,
        "elapsed_seconds": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "error": None,
    }


def check_health(url: str, timeout: int = 10) -> dict[str, Any]:
    """Return the /health payload, or raise on failure."""
    resp = requests.get(
        f"{url}/health", timeout=timeout, proxies={"http": None, "https": None}
    )
    resp.raise_for_status()
    return resp.json()
