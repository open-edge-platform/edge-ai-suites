#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""LLM caller — streams scene window text to Ollama; calls listeners per token.

Each call cycle:
  1. Get current window_text() from the Narrator
  2. POST to Ollama /api/chat with streaming enabled
  3. Call token listeners on every token received
  4. When response completes, detect severity and call listeners with done=True
  5. Immediately begin the next cycle (back-off 2s if window empty or call fails)

Usage as library:
  from llm_caller import LLMCaller, PRESETS
  caller = LLMCaller(narrator, ollama_url=os.environ["OLLAMA_URL"])
  caller.add_listener(lambda token, done, sev: ...)
  caller.start(prompt=PRESETS["Security Watch"])
"""

import json
import logging
import os
import threading
import time

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL   = os.environ.get("OLLAMA_URL", "")
OLLAMA_MODEL = "qwen2.5:7b"

# ── Canned system-prompt presets ────────────────────────────────────────────────

PRESETS: dict[str, str] = {
  "Security Watch": (
    "You are a security analyst monitoring a smart building in real time.\n"
    "Review the scene data and flag: credential violations (people crossing Checkpoint "
    "without badge/face ID), suspicious loitering (stationary >2 min in restricted "
    "areas), and unattended luggage (no companion for >30s).\n"
    "Be specific, factual, and concise. Mention person labels and locations.\n"
    "Begin your response with exactly one of: [INFO], [WARNING], or [ALERT]."
  ),
  "Occupancy Summary": (
    "You are a facility manager reviewing occupancy in a smart building.\n"
    "Summarise who is in each zone, how long they have been there, and the total "
    "headcount. Note any zones that seem unusually crowded or empty.\n"
    "Begin your response with exactly one of: [INFO], [WARNING], or [ALERT]."
  ),
  "Fallen Person": (
    "You are a safety monitor watching for persons in distress.\n"
    "Look for anyone reported with 'horizontal' posture who is NOT in a furniture "
    "region such as Couch. A horizontal posture outside a furniture area may indicate "
    "a fall. Call out the person label and their location.\n"
    "Begin your response with exactly one of: [INFO], [WARNING], or [ALERT]."
  ),
  "Stolen Luggage": (
    "You are a loss-prevention officer tracking baggage in a smart building.\n"
    "Report any luggage that has been left without a companion for more than 30 "
    "seconds, or luggage whose companion has changed unexpectedly. Flag luggage "
    "moving without a clear companion.\n"
    "Begin your response with exactly one of: [INFO], [WARNING], or [ALERT]."
  ),
  "Luggage Switch": (
    "You are monitoring for deliberate luggage exchange or substitution.\n"
    "Watch specifically for CHANGE events in the data where luggage changes companion. "
    "Flag any case where luggage moves from one person to another, noting who was "
    "involved and whether either person had credentials.\n"
    "Begin your response with exactly one of: [INFO], [WARNING], or [ALERT]."
  ),
}

DEFAULT_PRESET = "Security Watch"

# ── Fixed prompt for alert descriptions ─────────────────────────────────────────
ALERT_DESCRIBE_PROMPT = (
  "You are a security officer receiving an automated alert from a smart building system.\n"
  "Write a 2-3 sentence entry for the security log describing what happened.\n"
  "Translate the technical data into plain English: include the time, what occurred, "
  "the position/region, and which cameras can see the person or object.\n"
  "Do not repeat raw notation — interpret it. Be factual and concise.\n"
  "Begin with exactly one of: [INFO], [WARNING], or [ALERT]."
)


# ── LLMCaller ───────────────────────────────────────────────────────────────────

class LLMCaller:
  """Streams scene narrative to Ollama continuously; calls listeners per token."""

  def __init__(self, narrator, ollama_url: str | None = None,
               model: str = OLLAMA_MODEL):
    self._narrator = narrator
    resolved_url = (ollama_url or OLLAMA_URL).rstrip("/")
    if not resolved_url:
      raise ValueError("OLLAMA_URL must be set or passed explicitly")
    self._url      = resolved_url
    self._model    = model
    self._running  = False
    self._thread: threading.Thread | None = None
    self._lock     = threading.Lock()

    self._prompt: str = PRESETS[DEFAULT_PRESET]

    # Listeners: callable(token: str, done: bool, severity: str | None)
    #   token    — text fragment (empty string when done=True)
    #   done     — True on the final call for this response cycle
    #   severity — "INFO" | "WARNING" | "ALERT" (only set when done=True)
    self._listeners: list = []
    self._alert_busy: bool = False

  # ── Public API ────────────────────────────────────────────────────────────────

  def add_listener(self, cb) -> None:
    """Register a callback(token, done, severity) called on every token."""
    self._listeners.append(cb)

  def set_prompt(self, text: str) -> None:
    """Update the system prompt used by the next call cycle."""
    with self._lock:
      self._prompt = text

  def start(self, prompt: str | None = None) -> None:
    """Start the continuous call loop. No-op if already running."""
    if prompt is not None:
      with self._lock:
        self._prompt = prompt
    with self._lock:
      if self._running:
        return
      self._running = True
    self._thread = threading.Thread(target=self._loop, daemon=True)
    self._thread.start()
    logger.info("LLMCaller started")

  def stop(self) -> None:
    """Signal the call loop to stop after the current response finishes."""
    with self._lock:
      self._running = False
    logger.info("LLMCaller stopping")

  @property
  def running(self) -> bool:
    with self._lock:
      return self._running

  # ── Internal ─────────────────────────────────────────────────────────────────

  def _notify(self, token: str, done: bool, severity: str | None = None) -> None:
    for cb in self._listeners:
      try:
        cb(token, done, severity)
      except Exception:
        logger.exception("LLM listener error")

  @staticmethod
  def _detect_severity(text: str) -> str:
    t = text.lstrip()
    if t.startswith("[ALERT]"):
      return "ALERT"
    if t.startswith("[WARNING]"):
      return "WARNING"
    return "INFO"

  @property
  def busy(self) -> bool:
    """True while an alert description call is in progress."""
    with self._lock:
      return self._alert_busy

  def describe_alert(self, alert_text: str, context: str = "") -> bool:
    """Non-blocking: fire a one-shot LLM description of a specific alert.

    Returns True if the call was accepted, False if one is already in progress.
    alert_text — the raw alert entry from the narrator
    context    — optional recent scene window for background
    """
    with self._lock:
      if self._alert_busy:
        return False
      self._alert_busy = True
    threading.Thread(
      target=self._call_alert,
      args=(alert_text, context),
      daemon=True,
    ).start()
    return True

  def _call_alert(self, alert_text: str, context: str) -> None:
    """Blocking: stream one alert description to Ollama, notify listeners."""
    user_msg = f"Alert:\n{alert_text}"
    if context:
      user_msg += f"\n\nRecent scene context:\n{context}"

    payload = {
      "model": self._model,
      "stream": True,
      "messages": [
        {"role": "system", "content": ALERT_DESCRIBE_PROMPT},
        {"role": "user",   "content": user_msg},
      ],
    }

    full: list[str] = []
    try:
      with httpx.stream(
        "POST", f"{self._url}/api/chat",
        json=payload, timeout=None,
      ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
          if not line:
            continue
          chunk = json.loads(line)
          token = chunk.get("message", {}).get("content", "")
          if token:
            full.append(token)
            self._notify(token, False)
    except Exception:
      logger.exception("Ollama alert call failed")
      return

    full_text = "".join(full)
    self._notify("", True, self._detect_severity(full_text))
    with self._lock:
      self._alert_busy = False

  def _call_once(self, system_prompt: str) -> str:
    """One streaming call to Ollama. Returns full response text, or '' on error."""
    window = self._narrator.window_text()
    if not window.strip():
      return ""

    payload = {
      "model": self._model,
      "stream": True,
      "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": window},
      ],
    }

    full: list[str] = []
    try:
      with httpx.stream(
        "POST", f"{self._url}/api/chat",
        json=payload, timeout=None,
      ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
          if not line:
            continue
          with self._lock:
            still_running = self._running
          if not still_running:
            break
          chunk = json.loads(line)
          token = chunk.get("message", {}).get("content", "")
          if token:
            full.append(token)
            self._notify(token, False)
    except Exception:
      logger.exception("Ollama call failed")
      return ""

    full_text = "".join(full)
    severity  = self._detect_severity(full_text)
    self._notify("", True, severity)
    return full_text

  def _loop(self) -> None:
    while True:
      with self._lock:
        if not self._running:
          break
        prompt = self._prompt
      text = self._call_once(prompt)
      if not text:
        time.sleep(2)   # brief back-off when window is empty or call failed
