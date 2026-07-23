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


def encode_image(path: "Path | PIL.Image.Image", max_pixels: int | None = None) -> str:
    """Base64 data-URL for an image (Path or in-memory PIL Image).

    If max_pixels is set and the image exceeds it, downscale before encoding.
    """
    from io import BytesIO
    from PIL import Image as _PILImage

    if isinstance(path, _PILImage.Image):
        im = path.convert("RGB")
    else:
        im = _PILImage.open(path).convert("RGB")

    w, h = im.size
    if max_pixels and w * h > max_pixels:
        scale = (max_pixels / (w * h)) ** 0.5
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                       _PILImage.Resampling.LANCZOS)

    buf = BytesIO()
    im.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def build_payload(image: "Path | PIL.Image.Image", user_prompt: str,
                  max_tokens: int, temperature: float,
                  max_image_pixels: int | None = None) -> dict[str, Any]:
    return {
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
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }


def grade_page(
    url: str,
    image: "Path | PIL.Image.Image",
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
    payload = build_payload(image, user_prompt, max_tokens, temperature,
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
    usage = data.get("usage") or {}
    return {
        "ok": True,
        "answer": answer,
        "elapsed_seconds": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "error": None,
    }


HEADER_SYSTEM_PROMPT = (
    "You extract identifying information from the header of a scanned exam paper. "
    "You are given the first page of an exam. Read only the header area (title band "
    "and any candidate-information line); ignore the questions. Return a single JSON "
    "object and nothing else, with exactly these keys: "
    "paper_title (the exam paper title, e.g. the full name printed at the top), "
    "subject (the subject, e.g. 数学/语文/英语), "
    "student_name (the candidate's name), "
    "class_name (the candidate's class), "
    "exam_number (the candidate's exam/admission number). "
    "If a field is not present on the page, set its value to null. "
    "Do not invent values. Output only the JSON object."
)


def extract_header_info(
    url: str,
    image: "Path | PIL.Image.Image",
    instruction: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.0,
    timeout: int = 300,
    max_image_pixels: int | None = None,
) -> dict[str, Any]:
    user_text = (
        instruction.strip()
        if instruction and instruction.strip()
        else "Extract the header information as the specified JSON object."
    )
    payload = {
        "messages": [
            {"role": "system", "content": HEADER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": encode_image(image, max_image_pixels)}},
                    {"type": "text", "text": user_text},
                ],
            },
        ],
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }

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
    return {
        "ok": True,
        "answer": choice.get("message", {}).get("content", ""),
        "elapsed_seconds": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "error": None,
    }


def check_health(url: str, timeout: int = 10) -> dict[str, Any]:
    """Return the /health payload, or raise on failure."""
    resp = requests.get(
        f"{url}/health", timeout=timeout, proxies={"http": None, "https": None}
    )
    resp.raise_for_status()
    return resp.json()
