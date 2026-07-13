from __future__ import annotations

import io
import json as _json
import os
import threading
import time
import urllib.parse as _urlparse
import wave
from datetime import datetime
from typing import Any, Generator
from urllib.parse import urlparse

import gradio as gr
import httpx
import numpy as np
import plotly.graph_objects as go

from kiosk_core import config as kiosk_config

# ── Config ────────────────────────────────────────────────────────────────────
KIOSK_CORE_URL          = os.getenv("KIOSK_CORE_UI_BASE_URL",           "http://127.0.0.1:8012")
RAG_URL                 = os.getenv("KIOSK_CORE_UI_RAG_URL",            "http://127.0.0.1:8020/api/v1/query")
TTS_URL                 = os.getenv("KIOSK_CORE_UI_TTS_URL",            "http://127.0.0.1:8011/v1/audio/speech")
ANALYZER_URL            = os.getenv("KIOSK_CORE_UI_ANALYZER_URL",       "http://127.0.0.1:8010/v1/audio/transcriptions")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("KIOSK_CORE_UI_TIMEOUT_SECONDS",       "120.0"))
POLL_INTERVAL_SECONDS   = float(os.getenv("KIOSK_CORE_UI_POLL_INTERVAL_SECONDS", "0.35"))
PERF_REFRESH_SECONDS    = float(os.getenv("KIOSK_CORE_UI_PERF_REFRESH_SECONDS", "1.0"))
_CHUNK_SECONDS          = kiosk_config.DEFAULT_CHUNK_SECONDS
_SAMPLE_KB_DIR          = os.path.join(os.path.dirname(__file__), "knowledge-base-samples")
_SAMPLE_KB_OPTIONS      = {
    "QuickBite (QSR)": os.path.join(_SAMPLE_KB_DIR, "QuickBite-M.md"),
    "MegaRetail (Retail Store)": os.path.join(_SAMPLE_KB_DIR, "MegaRetail-M.md"),
    "SkyJet (Airline)": os.path.join(_SAMPLE_KB_DIR, "SkyJet-S.md"),
}
_DEFAULT_SAMPLE_KB      = next(iter(_SAMPLE_KB_OPTIONS))
_LAST_METRICS_PAYLOAD: dict[str, Any] = {}

# ── Derived base URLs for KPI endpoints ──────────────────────────────────────
def _svc_base(full_url: str) -> str:
    p = urlparse(full_url)
    return f"{p.scheme}://{p.netloc}"

_ANALYZER_BASE = _svc_base(ANALYZER_URL)
_TTS_BASE      = _svc_base(TTS_URL)
_RAG_BASE      = _svc_base(RAG_URL)

# ── CSS (only targets our own divs + minimal Gradio overrides) ────────────────
STYLE = """
/*
 * Intel Light Theme
 *   bg-base  #FFFFFF   page — clean white
 *   bg-1     #F4F7FB   chat pane — very light blue-grey
 *   bg-2     #EBF2FA   assistant bubble — soft Intel blue tint
 *   border   #C8D8EA   Intel blue-grey border
 *   user-bub #0068B5   Intel Blue
 *   text-hi  #1A1A1A   near-black body text
 *   text-md  #4A6070   Intel blue-grey secondary
 *   text-lo  #8FA0AE   muted
 *   accent   #0068B5   Intel Blue
 */

/* Page */
.gradio-container { background: #FFFFFF !important; }
footer { display: none !important; }

/* Layout */
.kiosk-row   { width: 100% !important; align-items: flex-start !important; gap: 16px !important; }
.kiosk-left  { min-width: 0 !important; }
.kiosk-right { width: 340px !important; min-width: 280px !important; max-width: 360px !important; flex-shrink: 0 !important; }

/* ── Compact file upload widgets inside the right-panel accordions ── */
.kiosk-right .file-preview,
.kiosk-right [data-testid="file"],
.kiosk-right .upload-container {
    min-height: 0 !important;
}
.kiosk-right .file-preview,
.kiosk-right [data-testid="file"] {
    padding: 6px 8px !important;
    font-size: 0.74rem !important;
}
.kiosk-right .upload-container,
.kiosk-right .file-preview .download {
    padding: 4px 6px !important;
}
/* The big drag-and-drop drop zone — compress its vertical footprint */
.kiosk-right .wrap.svelte-1ipelgc,
.kiosk-right .wrap[class*="svelte"]:has(input[type="file"]),
.kiosk-right [data-testid="file"] .wrap,
.kiosk-right .upload-container .wrap,
.kiosk-right .file-preview,
.kiosk-right .file-preview .wrap {
    min-height: 32px !important;
    height: 32px !important;
    padding: 4px 8px !important;
    font-size: 0.72rem !important;
    line-height: 1.1 !important;
}
/* Hide the big "Drop File Here / or Click to Upload" hint block so the
   zone collapses to just the icon + filename row */
.kiosk-right .file-preview .or,
.kiosk-right [data-testid="file"] .or,
.kiosk-right .upload-container .or {
    display: none !important;
}
.kiosk-right .file-preview .wrap > *,
.kiosk-right [data-testid="file"] .wrap > * {
    margin: 0 !important;
}
.kiosk-right input[type="file"] + * .icon,
.kiosk-right .upload-container svg {
    width: 18px !important;
    height: 18px !important;
}
/* Tighten the label rows above the file widgets */
.kiosk-right .label-wrap span,
.kiosk-right label > span {
    font-size: 0.74rem !important;
}

/* Chat pane */
.chat-pane {
    height: 420px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px 10px;
    background: #F4F7FB;
    border-radius: 12px;
    border: 1px solid #C8D8EA;
    scroll-behavior: smooth;
}
.chat-pane::-webkit-scrollbar { width: 4px; }
.chat-pane::-webkit-scrollbar-thumb { background: #C8D8EA; border-radius: 4px; }
.chat-empty { margin: auto; color: #8FA0AE; font-size: 0.85rem; font-style: italic; }

/* Bubbles */
.msg-row { display: flex; align-items: flex-end; gap: 8px; }
.msg-row.user { flex-direction: row-reverse; }

.bubble {
    max-width: 75%;
    padding: 10px 15px;
    border-radius: 18px;
    font-size: 0.93rem;
    line-height: 1.6;
    word-break: break-word;
    font-family: Inter, "Segoe UI", system-ui, sans-serif;
}
.msg-row.user .bubble {
    background: #0068B5;
    color: #FFFFFF;
    border-bottom-right-radius: 4px;
}
.msg-row.asst .bubble {
    background: #EBF2FA;
    color: #1A1A1A;
    border: 1px solid #C8D8EA;
    border-bottom-left-radius: 4px;
}
.bubble.partial { opacity: 0.65; }
.cursor {
    display: inline-block;
    color: #0068B5;
    animation: blink 0.9s step-end infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* Status */
.status-line {
    text-align: center;
    color: #4A6070;
    font-size: 0.78rem;
    font-family: Inter, "Segoe UI", system-ui, sans-serif;
    min-height: 20px;
}

/* Status row — status line on the left, Kiosk Assist pill on the right */
.status-row {
    width: 100% !important;
    align-items: center !important;
    gap: 12px !important;
    margin: 6px 0 !important;
    flex-wrap: nowrap !important;
}
.status-row > div:first-child { flex: 1 1 auto !important; min-width: 0 !important; }
.status-row .status-line { text-align: left !important; min-height: 0 !important; }
.status-tts-col {
    flex: 0 0 auto !important;
    max-width: 200px !important;
    min-width: 0 !important;
    padding: 0 !important;
}
/* When TTS lives in the status row, strip its block chrome and let the
   indicator pill flow inline instead of being absolutely centered. */
.status-tts-col #kiosk-tts,
.status-tts-col #kiosk-tts > .block {
    background: transparent !important;
    border: none !important;
    border-left: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-height: 0 !important;
    height: auto !important;
}
.status-tts-col #kiosk-tts .kiosk-tts-indicator {
    position: static !important;
    transform: none !important;
    margin: 0 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
    padding: 0 14px !important;
    height: 32px !important;
    min-height: 32px !important;
    font-size: 0.78rem !important;
}
.status-tts-col #kiosk-tts .kiosk-tts-icon,
.status-tts-col #kiosk-tts .kiosk-tts-icon svg {
    width: 18px !important;
    height: 18px !important;
}
.status-tts-col #kiosk-tts .kiosk-tts-title { font-size: 0.78rem !important; }

/* Headings */
.gradio-container h1, .gradio-container h2, .gradio-container h3,
.gradio-container .prose h1, .gradio-container .prose h2 {
    color: #1A1A1A !important;
}

/* ═══════════════════════════════════════════════════════════
   AUDIO CONTROL STRIP  —  one unified card
   Left half : mic selector + record button
   Right half : speaker icon → waveform player when audio plays
   ═══════════════════════════════════════════════════════════ */

/* The row itself becomes the single card. Width is locked to 100% of the
   left column so it lines up exactly with the chat-pane above. */
.audio-pair {
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    margin: 6px 0 !important;
    gap: 0 !important;
    align-items: stretch !important;
    flex-wrap: nowrap !important;
    background: linear-gradient(160deg, #EEF5FF 0%, #E6F0FA 100%) !important;
    border: 1.5px solid #C8D8EA !important;
    border-radius: 16px !important;
    box-shadow: 0 2px 8px rgba(0,104,181,0.07) !important;
    overflow: hidden !important;
    min-height: 120px !important;
}
.audio-pair > div {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    align-self: stretch !important;
    min-height: 120px !important;
}
/* Inside each column, force the gr.Audio root and its block to fill the
   column's full height so vertical centering actually has room to work */
.audio-pair > div > #kiosk-mic,
.audio-pair > div > #kiosk-tts,
.audio-pair > div > .form,
.audio-pair > div > .form > #kiosk-mic,
.audio-pair > div > .form > #kiosk-tts {
    flex: 1 1 auto !important;
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
}

/* Strip individual card styling from both blocks — they live inside the row card */
#kiosk-mic,
#kiosk-tts {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
#kiosk-mic > .block,
#kiosk-tts > .block {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 16px 14px !important;
    height: 100% !important;
    box-sizing: border-box !important;
}
#kiosk-mic > .block {
    display: block !important;
    position: relative !important;
    min-height: 120px !important;
}
/* Center the Speak/Stop button vertically and span the full width of the
   audio-pair card (no TTS half to share with anymore). */
#kiosk-mic .controls,
#kiosk-mic .recording-container,
#kiosk-mic .minimal-audio-player {
    position: absolute !important;
    top: 50% !important;
    left: 14px !important;
    right: 14px !important;
    transform: translateY(-50%) !important;
    margin: 0 !important;
    width: auto !important;
    height: auto !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ── Recorder teleport ──
   When recording starts, Gradio swaps the Speak button for a recorder UI
   (waveform canvas + Stop button). Svelte re-inserts nodes if we delete
   them, and inline styles defeat plain CSS hiding. So we:
     1) move the actual Stop button into our own .kiosk-stop-host wrapper
     2) push the original recorder container off-screen (it keeps living
        in the DOM so Svelte's bindings stay intact). */
#kiosk-mic .kiosk-stop-host {
    position: absolute !important;
    top: 50% !important;
    left: 14px !important;
    right: 14px !important;
    transform: translateY(-50%) !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 8px !important;
    z-index: 5 !important;
    pointer-events: auto !important;
}
#kiosk-mic .kiosk-stop-host:empty { display: none !important; }
#kiosk-mic .kiosk-stop-host button {
    background: #D32F2F !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 999px !important;
    width: 80% !important;
    max-width: 460px !important;
    margin: 0 auto !important;
    height: 44px !important;
    min-width: 140px !important;
    padding: 0 22px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    box-shadow: 0 3px 12px rgba(211,47,47,0.32) !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
}
#kiosk-mic .kiosk-stop-host button:hover {
    background: #B71C1C !important;
    transform: scale(1.06) !important;
    box-shadow: 0 5px 18px rgba(211,47,47,0.45) !important;
}
#kiosk-mic .kiosk-stop-host button svg {
    stroke: #FFFFFF !important;
    fill: #FFFFFF !important;
    width: 18px !important;
    height: 18px !important;
}
/* The original recorder container — physically teleported into
   #kiosk-recorder-bin (attached to <body>). Keep it visible there so you
   can confirm it actually moved; collapse it to a small footprint. */
#kiosk-recorder-bin {
    position: fixed !important;
    right: 16px !important;
    bottom: 16px !important;
    z-index: 9999 !important;
    width: 260px !important;
    min-height: 110px !important;
    max-width: 80vw !important;
    background: #FFFFFF !important;
    border: 1px solid #C8D8EA !important;
    border-radius: 12px !important;
    box-shadow: 0 6px 24px rgba(0,0,0,0.12) !important;
    padding: 12px 14px !important;
    font-family: Inter, "Segoe UI", system-ui, sans-serif !important;
    color: #1A1A1A !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
}
#kiosk-recorder-bin > * {
    align-self: stretch !important;
    margin: auto 0 !important;
}
#kiosk-recorder-bin:empty { display: none !important; }
#kiosk-recorder-bin::before {
    content: "🎙 Live recording";
    display: block;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #0068B5;
    margin-bottom: 6px;
}
#kiosk-recorder-bin canvas,
#kiosk-recorder-bin .canvases,
#kiosk-recorder-bin .waveform-container {
    max-width: 100% !important;
    width: 100% !important;
    height: 48px !important;
    background: #F4F7FB !important;
    border-radius: 6px !important;
}
/* Hide any non-stop controls that hitched a ride into the bin */
#kiosk-recorder-bin .controls,
#kiosk-recorder-bin button {
    display: none !important;
}
/* Vertical divider between mic and TTS halves */
#kiosk-tts > .block {
    border-left: 1px solid #C8D8EA !important;
    min-height: 90px !important;
}

/* Hide labels on both audio widgets */
#kiosk-mic label, #kiosk-mic .label-wrap, #kiosk-mic [data-testid="label"],
#kiosk-tts label, #kiosk-tts .label-wrap, #kiosk-tts [data-testid="label"] {
    display: none !important;
}

/* ── Mic half ── */
#kiosk-mic .minimal-audio-player,
#kiosk-mic .wrapper,
#kiosk-mic .waveform-wrapper {
    width: 100% !important;
    min-height: 76px !important;
    height: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
#kiosk-mic .canvases,
#kiosk-mic .progress,
#kiosk-mic .scroll,
#kiosk-mic .cursor,
#kiosk-mic .timestamp {
    align-self: center !important;
}
#kiosk-mic .waveform-container,
#kiosk-mic .recording-container {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
    min-height: 76px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
#kiosk-mic .controls,
#kiosk-mic .waveform-container .controls {
    background: transparent !important;
    gap: 8px !important;
    padding: 4px 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-wrap: wrap !important;
    width: 100% !important;
    margin: 0 auto !important;
}
#kiosk-mic .controls button,
#kiosk-mic .waveform-container button,
#kiosk-mic .recording-container button {
    background: #0068B5 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 999px !important;
    width: 80% !important;
    max-width: 460px !important;
    margin: 0 auto !important;
    height: 44px !important;
    min-width: 140px !important;
    padding: 0 22px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    white-space: nowrap !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    box-shadow: 0 3px 12px rgba(0,104,181,0.32) !important;
    transition: background 0.15s ease, transform 0.12s ease, box-shadow 0.15s ease !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
}
#kiosk-mic .controls button:hover,
#kiosk-mic .waveform-container button:hover,
#kiosk-mic .recording-container button:hover {
    background: #005A9E !important;
    transform: scale(1.06) !important;
    box-shadow: 0 5px 18px rgba(0,104,181,0.45) !important;
}
#kiosk-mic .controls button svg,
#kiosk-mic .waveform-container button svg,
#kiosk-mic .recording-container button svg {
    stroke: #FFFFFF !important;
    fill: #FFFFFF !important;
    width: 24px !important; height: 24px !important;
}
#kiosk-mic select {
    background: rgba(255,255,255,0.7) !important;
    border: 1px solid #C8D8EA !important;
    border-radius: 8px !important;
    color: #1A1A1A !important;
    font-size: 0.76rem !important;
    padding: 4px 10px !important;
    box-shadow: none !important;
    outline: none !important;
    cursor: pointer !important;
    width: 100% !important;
    margin-bottom: 6px !important;
}
#kiosk-mic select:focus {
    border-color: #0068B5 !important;
    box-shadow: 0 0 0 2px rgba(0,104,181,0.15) !important;
}
/* Hide the device selector from the left card (it lives in the Mic Device accordion) */
#kiosk-mic select {
    display: none !important;
}
/* Style the select once it's moved into the right-panel accordion */
/* Ensure the whole ancestor chain is full-width so 100% resolves correctly */
#mic-device-panel {
    width: 100% !important;
    box-sizing: border-box !important;
    display: block !important;
}
/* The gr.HTML block Gradio wraps around our div */
#mic-device-panel > *,
#mic-device-panel + * {
    width: 100% !important;
    box-sizing: border-box !important;
}
#mic-device-panel select {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    margin-top: 8px !important;
    background: #FFFFFF !important;
    border: 1px solid #C8D8EA !important;
    border-radius: 8px !important;
    color: #1A1A1A !important;
    font-size: 0.82rem !important;
    padding: 7px 10px !important;
    box-shadow: none !important;
    outline: none !important;
    cursor: pointer !important;
    min-width: 0 !important;
}
#mic-device-panel select:focus {
    border-color: #0068B5 !important;
    box-shadow: 0 0 0 2px rgba(0,104,181,0.15) !important;
}
/* Reset/clear button — small ghost, turns red on hover to signal destructive
   Uses more specific selector (.controls [aria-label]) to override width:100% */
#kiosk-mic .controls [aria-label="Reset audio"],
#kiosk-mic .waveform-container [aria-label="Reset audio"],
#kiosk-mic .recording-container [aria-label="Reset audio"] {
    background: rgba(255,255,255,0.55) !important;
    color: #8FA0AE !important;
    width: 28px !important;
    height: 28px !important;
    min-width: 28px !important;
    padding: 0 !important;
    border-radius: 50% !important;
    border: 1px solid #C8D8EA !important;
    box-shadow: none !important;
}
#kiosk-mic .controls [aria-label="Reset audio"]:hover,
#kiosk-mic .waveform-container [aria-label="Reset audio"]:hover,
#kiosk-mic .recording-container [aria-label="Reset audio"]:hover {
    background: rgba(211,47,47,0.08) !important;
    color: #D32F2F !important;
    border-color: rgba(211,47,47,0.35) !important;
    transform: scale(1.05) !important;
    box-shadow: none !important;
}
#kiosk-mic .controls [aria-label="Reset audio"] svg,
#kiosk-mic .waveform-container [aria-label="Reset audio"] svg,
#kiosk-mic .recording-container [aria-label="Reset audio"] svg {
    stroke: currentColor !important;
    fill: none !important;
    width: 13px !important;
    height: 13px !important;
}

/* ── Assistant / TTS half ── */
#kiosk-tts .waveform-container {
    background: transparent !important;
    border: none !important;
    padding: 2px 0 !important;
    min-height: 76px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
/* .block must be relative so the absolute-positioned indicator resolves against it */
#kiosk-tts > .block {
    display: block !important;
    position: relative !important;
}
/* All Gradio intermediate wrappers between .block and our indicator: make them
   fill the full block height but do NOT introduce their own alignment so only
   our absolute centering takes effect */
#kiosk-tts > .block > *:not(.kiosk-tts-indicator):not(audio) {
    position: static !important;
    display: block !important;
    height: 100% !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}
/* The indicator is absolutely centered inside .block, exactly like the Speak button */
#kiosk-tts .kiosk-tts-indicator {
    position: absolute !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    margin: 0 !important;
}
#kiosk-tts audio,
#kiosk-tts .controls,
#kiosk-tts .play-pause-button,
#kiosk-tts button.icon,
#kiosk-tts input[type=range],
#kiosk-tts .timestamps,
#kiosk-tts .timestamp,
#kiosk-tts .waveform-container,
#kiosk-tts [aria-label="Empty value"] {
    display: none !important;
}
#kiosk-tts .kiosk-tts-indicator {
    width: min(100%, 220px);
    height: 40px;
    min-width: 40px;
    min-height: 40px;
    margin: 0 auto;
    padding: 0 16px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: #0068B5;
    color: #FFFFFF;
    border: none;
    box-shadow: 0 3px 12px rgba(0,104,181,0.32);
    box-sizing: border-box;
    white-space: nowrap;
    overflow: hidden;
}
#kiosk-tts .kiosk-tts-icon {
    width: 24px;
    height: 24px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transform-origin: center bottom;
    flex: 0 0 auto;
}
#kiosk-tts .kiosk-tts-icon svg {
    width: 24px;
    height: 24px;
    fill: #FFFFFF;
    stroke: #FFFFFF;
}
#kiosk-tts .kiosk-tts-title {
    color: #FFFFFF;
    font-size: 0.85rem;
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
#kiosk-tts .kiosk-tts-subtitle {
    display: none;
}
#kiosk-tts .kiosk-tts-bars {
    display: none;
}
#kiosk-tts .kiosk-tts-bars span {
    width: 3px;
    height: 7px;
    border-radius: 999px;
    background: #8DB6D8;
    opacity: 0.7;
    transform-origin: center bottom;
}
#kiosk-tts.kiosk-tts-queued .kiosk-tts-icon,
#kiosk-tts.kiosk-tts-playing .kiosk-tts-icon {
    animation: tts-bounce 0.95s ease-in-out infinite;
}
#kiosk-tts.kiosk-tts-playing .kiosk-tts-icon {
    transform: scale(1.04);
}
#kiosk-tts.kiosk-tts-queued .kiosk-tts-subtitle::before {
    content: "Kiosk Speaking";
}
#kiosk-tts.kiosk-tts-playing .kiosk-tts-subtitle::before {
    content: "Kiosk Speaking";
}
#kiosk-tts.kiosk-tts-idle .kiosk-tts-subtitle::before {
    content: "Ready to respond";
}
@keyframes tts-bounce {
    0%, 100% { transform: translateY(0) scale(1); }
    35% { transform: translateY(-7px) scale(1.03); }
    65% { transform: translateY(0) scale(0.985); }
}
@keyframes tts-bars {
    0%, 100% { transform: scaleY(0.7); }
    40% { transform: scaleY(1.8); }
    70% { transform: scaleY(1.15); }
}

/* Remaining Gradio shell overrides */
.gradio-container .block,
.gradio-container .wrap,
.gradio-container .form,
.gradio-container fieldset,
.gradio-container .panel {
    background: #FFFFFF !important;
    border-color: #C8D8EA !important;
}
.gradio-container .waveform-container,
.gradio-container .recording-container,
.gradio-container .controls {
    background: #F4F7FB !important;
    color: #1A1A1A !important;
}
.gradio-container details,
.gradio-container details > summary {
    background: #FFFFFF !important;
    border-color: #C8D8EA !important;
    color: #1A1A1A !important;
}
.gradio-container details[open] > div {
    background: #F4F7FB !important;
    border-color: #C8D8EA !important;
}
.gradio-container label span,
.gradio-container .label-wrap span {
    color: #4A6070 !important;
}

/* ── KPI panel ── */
.kpi-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 4px 0;
}
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #C8D8EA;
    border-left: 3px solid #0068B5;
    border-radius: 10px;
    padding: 12px 14px;
    font-family: Inter, "Segoe UI", system-ui, sans-serif;
}
.kpi-card-title {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #0068B5;
    margin-bottom: 8px;
}
.kpi-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 3px 0;
    border-bottom: 1px solid #EBF2FA;
}
.kpi-row:last-child { border-bottom: none; }
.kpi-key {
    font-size: 0.75rem;
    color: #4A6070;
    white-space: nowrap;
    margin-right: 8px;
}
.kpi-val {
    font-size: 0.78rem;
    color: #1A1A1A;
    font-weight: 500;
    text-align: right;
    word-break: break-all;
}
.kpi-badge {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.badge-green  { background: #D4F5E5; color: #0A6640; }
.badge-blue   { background: #D0E8F8; color: #004E8C; }
.badge-purple { background: #E8D8F8; color: #5E2D9E; }

/* Hidden Gradio component that stays in the DOM (so JS .click() reaches
   Gradio's event handler) but is invisible to users. */
.kiosk-hidden { display: none !important; }

/* ── Knowledge-base ingest panel ── */
.ingest-note {
    font-size: 0.74rem;
    color: #4A6070;
    line-height: 1.6;
    padding: 10px 12px;
    background: #F4F7FB;
    border-radius: 8px;
    border-left: 3px solid #0068B5;
    margin-bottom: 10px;
}
.ingest-note strong { color: #1A1A1A; }
.ingest-status {
    font-size: 0.78rem;
    padding: 8px 12px;
    border-radius: 8px;
    margin-top: 8px;
    min-height: 0;
}
.ingest-status.loading { background: #EBF2FA; color: #004E8C; border: 1px solid #C8D8EA; }
.ingest-status.success { background: #D4F5E5; color: #0A6640; border: 1px solid #A8E6C8; }
.ingest-status.error   { background: #FDECEA; color: #B71C1C; border: 1px solid #F5C6CB; }
.ingest-status.warn    { background: #FFF8E1; color: #795500; border: 1px solid #FFD966; }

/* While ingest is loading, grey the mic out so the user can't fire a question. */
.gradio-container:has(.ingest-status.loading) #kiosk-mic {
    pointer-events: none;
    opacity: 0.5;
    filter: grayscale(0.6);
}

/* ── Performance / Resource Utilization panel ── */
.perf-plot-row {
    gap: 8px !important;
    margin-bottom: 6px !important;
}
.perf-plot-row > div {
    min-width: 0 !important;
    flex: 1 1 0 !important;
}
/* Shrink the Plotly toolbar so it doesn't overflow the narrow right panel */
.kiosk-right .js-plotly-plot .plotly .modebar {
    right: 2px !important;
    top: 2px !important;
    transform: scale(0.8);
    transform-origin: top right;
}
"""

# ── Chat HTML helpers ─────────────────────────────────────────────────────────
def _esc(t: str) -> str:
    return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")


_INGEST_NOTE_HTML = """
<div class="ingest-note">
  Upload a <strong>.txt</strong> or <strong>.md</strong> file to update the assistant&#39;s knowledge base.
  Or pick a built-in sample knowledge base below and ingest it in one click.
  <strong>This replaces the existing knowledge base.</strong>
</div>
"""


def _selected_sample_path(sample_name: str | None) -> str | None:
    if not sample_name:
        return None
    return _SAMPLE_KB_OPTIONS.get(sample_name)


def _sample_download_value(sample_name: str | None) -> str | None:
    sample_path = _selected_sample_path(sample_name)
    return sample_path if sample_path and os.path.exists(sample_path) else None


def _ingest_doc_common(file, idle_upload_label: str = "📄 Upload .txt / .md & Ingest", idle_sample_label: str = "Use Sample & Ingest") -> Generator:
    """Clear the current knowledge base and ingest the selected document.

    Outputs are `[ingest_status, ingest_btn, sample_ingest_btn]` — the streaming
    `mic` is deliberately NOT an output of this handler. Pushing updates to a
    `streaming=True` `gr.Audio` from a foreign event makes its postprocess
    raise on the final render and the component shows a red ✕ error border
    until reload.
    """
    if file is None:
        yield (
            '<div class="ingest-status warn">⚠️ Please select a file first.</div>',
            gr.update(),
            gr.update(),
        )
        return

    # Immediately lock the mic and both ingest buttons while work is in progress
    loading_html = (
        '<div class="ingest-status loading">'
        '⏳ Ingesting knowledge base &#8212; the assistant will be back shortly&#8230;'
        '<br><small>This may take a few minutes depending on content size. '
        'Please do not refresh the page.</small>'
        '</div>'
    )
    # Lock both ingest buttons while work is in progress. Clear the
    # UploadButton's value (FileData) up-front: Gradio cleans up the uploaded
    # temp file shortly after the upload handler starts, so any later yield
    # that re-serialises the stored FileData raises in postprocess and the
    # button is flagged with a red ✕ error border until the page is reloaded.
    _INGEST_IN_PROGRESS.set()
    yield (
        loading_html,
        gr.update(value=None, interactive=False),
        gr.update(interactive=False, value="Ingesting…"),
    )

    filename = os.path.basename(file) if isinstance(file, str) else os.path.basename(file.name)
    filepath = file if isinstance(file, str) else file.name

    result_holder: dict[str, Any] = {}

    def _do_ingest() -> None:
        try:
            # 1. Wipe the existing knowledge base
            with httpx.Client(timeout=15.0, trust_env=False) as c:
                c.delete(f"{_RAG_BASE}/api/v1/context")

            # 2. Ingest the new document
            with open(filepath, "rb") as fh:
                content = fh.read()

            with httpx.Client(timeout=600.0, trust_env=False) as c:
                resp = c.post(
                    f"{_RAG_BASE}/api/v1/context/file",
                    files={"file": (filename, content, "text/plain")},
                )

            # Try to surface the server's error detail for non-2xx responses.
            if resp.status_code >= 400:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text or f"HTTP {resp.status_code}"
                result_holder["error"] = str(detail)
                return

            result_holder["data"] = resp.json()
        except Exception as exc:  # noqa: BLE001
            result_holder["error"] = str(exc)

    worker = threading.Thread(target=_do_ingest, daemon=True)
    worker.start()

    # Heartbeat: keep the SSE/WS connection alive while the worker runs so the
    # browser never sees a connection-error toast for long ingests. Use no-op
    # updates so we don't keep resetting the UploadButton / sample button.
    while worker.is_alive():
        worker.join(timeout=2.0)
        if worker.is_alive():
            yield (
                loading_html,
                gr.update(),
                gr.update(),
            )

    if "error" in result_holder:
        _INGEST_IN_PROGRESS.clear()
        yield (
            f'<div class="ingest-status error">'
            f'⚠️ Ingestion failed: {_esc(result_holder["error"])}. '
            f'The previous knowledge base remains active.'
            f'</div>',
            gr.update(value=None, interactive=True),
            gr.update(interactive=True, value=idle_sample_label),
        )
        return

    result = result_holder.get("data", {})
    chunks = result.get("chunks_added", "?")
    src    = result.get("source", filename)
    _INGEST_IN_PROGRESS.clear()
    yield (
        f'<div class="ingest-status success">'
        f'✅ Knowledge base updated &#8212; {chunks} chunks ingested from'
        f' &#34;{_esc(src)}&#34;. The assistant is ready.'
        f'</div>',
        gr.update(value=None, interactive=True),
        gr.update(interactive=True, value=idle_sample_label),
    )


def _ingest_doc(file) -> Generator:
    yield from _ingest_doc_common(file)


def _ingest_sample_doc(sample_name: str | None) -> Generator:
    sample_path = _selected_sample_path(sample_name)
    if sample_path is None:
        yield from _ingest_doc_common(None)
        return
    yield from _ingest_doc_common(sample_path)

def _render_chat(history: list[dict], partial_user: str = "", partial_asst: str = "") -> str:
    rows: list[str] = []
    for msg in history:
        cls = "user" if msg["role"] == "user" else "asst"
        rows.append(f'<div class="msg-row {cls}"><div class="bubble">{_esc(msg["text"])}</div></div>')
    if partial_user:
        rows.append(f'<div class="msg-row user"><div class="bubble partial">{_esc(partial_user)}</div></div>')
    if partial_asst:
        rows.append(
            f'<div class="msg-row asst"><div class="bubble partial">'
            f'{_esc(partial_asst)}<span class="cursor">▌</span></div></div>'
        )
    inner = "\n".join(rows) if rows else '<div class="chat-empty">Tap 🎤 and ask a question</div>'
    return f'<div class="chat-pane">{inner}<div class="chat-end-anchor" aria-hidden="true"></div></div>'

# ── API helpers ───────────────────────────────────────────────────────────────
def _numpy_to_wav(audio: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio.astype(np.int16).tobytes())
    return buf.getvalue()


def _to_int16_audio(data: np.ndarray) -> np.ndarray:
    """Normalize incoming Gradio audio to mono int16.

    Gradio can provide float32 samples in [-1, 1] or integer PCM depending on
    browser/runtime. Converting float directly with astype(int16) collapses most
    speech to zeros; scale first when data is floating-point.
    """
    if data.ndim > 1:
        data = data[:, 0]

    if np.issubdtype(data.dtype, np.floating):
        clipped = np.clip(data, -1.0, 1.0)
        return (clipped * 32767.0).astype(np.int16)

    if data.dtype != np.int16:
        return data.astype(np.int16)

    return data

def _recent_history_payload(history: list[dict] | None, max_turns: int = 4) -> list[dict[str, str]]:
    """Return the last `max_turns` chat turns in {role, content} form for the
    RAG service. `state["history"]` stores entries as {"role", "text"}; we
    rename `text` -> `content` and drop empties.
    """
    if not history:
        return []
    cleaned: list[dict[str, str]] = []
    for entry in history[-max_turns:]:
        role = str(entry.get("role", ""))
        content = str(entry.get("text", "")).strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def _open_session(sr: int, history: list[dict] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as c:
        r = c.post(f"{KIOSK_CORE_URL}/api/v1/sessions/start-stream", json={
            "sample_rate": sr,
            "chunk_seconds": kiosk_config.DEFAULT_CHUNK_SECONDS,  # 5.0s
            "silence_timeout_seconds": 2.0,
            "max_session_seconds": 60.0,
            "silence_threshold": 900,
            "language": "en", "temperature": 0.0,
            "analyzer_url": ANALYZER_URL, "rag_url": RAG_URL, "tts_url": TTS_URL,
            "tts_model": "speecht5", "tts_language": "English",
            "history": _recent_history_payload(history),
            "include_performance_metrics": True,
            "include_llm_metrics": True,
        })
    r.raise_for_status(); return r.json()

def _push(sid: str, wav: bytes) -> None:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as c:
        c.post(f"{KIOSK_CORE_URL}/api/v1/sessions/{sid}/audio",
               content=wav, headers={"Content-Type": "audio/wav"}).raise_for_status()

def _eos(sid: str) -> None:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as c:
        c.post(f"{KIOSK_CORE_URL}/api/v1/sessions/{sid}/audio/end").raise_for_status()

def _poll(sid: str) -> dict[str, Any]:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as c:
        r = c.get(f"{KIOSK_CORE_URL}/api/v1/sessions/{sid}")
    r.raise_for_status(); return r.json()

def _gradio_file_url(absolute_path: str) -> str:
    """Build the URL the browser uses to fetch a Gradio-served file."""
    encoded = _urlparse.quote(absolute_path, safe="/")
    return f"/gradio_api/file={encoded}"

# ── State ─────────────────────────────────────────────────────────────────────
_INIT: dict = {
    "session_id": None,
    "buffer": [],
    "sample_rate": 16000,
    "history": [],
    "stream_prev": None,
}

# Process-wide flag set while a knowledge-base ingest is running. The streaming
# mic events check this and become no-ops so users can't fire a question while
# the RAG service is rebuilding its index.
_INGEST_IN_PROGRESS = threading.Event()

# ── Handlers ──────────────────────────────────────────────────────────────────
def on_start(state: dict):
    if _INGEST_IN_PROGRESS.is_set():
        return state, gr.skip(), gr.update(value=None), gr.skip(), "⏳ Ingestion in progress — please wait…", gr.skip()
    s = dict(state); s["session_id"] = None; s["buffer"] = []; s["stream_prev"] = None
    return s, _render_chat(s["history"], partial_user="🎤  Listening…"), gr.update(value=None), gr.skip(), "🎙  Listening — speak now", gr.skip()


def _extract_new_stream_audio(prev_chunk: np.ndarray | None, current_chunk: np.ndarray) -> np.ndarray:
    if prev_chunk is None or len(prev_chunk) == 0:
        return current_chunk

    prev_len = len(prev_chunk)
    current_len = len(current_chunk)

    if current_len == prev_len and np.array_equal(current_chunk, prev_chunk):
        return np.empty(0, dtype=current_chunk.dtype)

    if current_len > prev_len and np.array_equal(current_chunk[:prev_len], prev_chunk):
        return current_chunk[prev_len:]

    return current_chunk

def on_chunk(state: dict, chunk):
    if _INGEST_IN_PROGRESS.is_set():
        return state, gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    if chunk is None:
        return state, gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    sr, data = chunk
    if data is None or len(data) == 0:
        return state, gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    data = _to_int16_audio(data)

    s = dict(state); s["sample_rate"] = sr
    new_data = _extract_new_stream_audio(s.get("stream_prev"), data)
    s["stream_prev"] = data.copy()
    if len(new_data) == 0:
        return s, gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()

    s["buffer"] = list(s.get("buffer", [])) + [new_data]

    if s["session_id"] is None:
        try:
            s["session_id"] = _open_session(sr, history=s.get("history"))["session_id"]
        except Exception as e:
            return s, gr.skip(), gr.skip(), gr.skip(), f"❌ {e}", gr.skip()

    total = sum(len(b) for b in s["buffer"])
    if total >= int(sr * _CHUNK_SECONDS):
        audio = np.concatenate(s["buffer"])
        try:
            _push(s["session_id"], _numpy_to_wav(audio, sr))
        except Exception:
            pass
        s["buffer"] = []

    transcript = ""
    try:
        transcript = str(_poll(s["session_id"]).get("transcript", "")).strip()
    except Exception: pass

    partial = transcript or "🎤  Listening…"
    return s, _render_chat(s["history"], partial_user=partial), gr.skip(), gr.skip(), "🎙  Listening — speak now", gr.skip()

def on_stop(state: dict, mic_value) -> Generator:
    s = dict(state)
    sid = s.get("session_id"); sr = s.get("sample_rate", 16000)
    history = list(s.get("history", []))
    seen = 0

    # Fallback path: when streaming chunk callbacks do not arrive (seen on some
    # remote/browser setups), use the final recorded clip emitted at stop.
    if not sid and mic_value is not None:
        try:
            fsr, fdata = mic_value
            if fdata is not None and len(fdata) > 0:
                fdata_i16 = _to_int16_audio(fdata)
                if len(fdata_i16) > 0:
                    sr = int(fsr or sr)
                    sid = _open_session(sr, history=s.get("history"))["session_id"]
                    _push(sid, _numpy_to_wav(fdata_i16, sr))
                    _eos(sid)
                    s["session_id"] = sid
                    s["sample_rate"] = sr
        except Exception:
            # Keep existing UX path below if fallback cannot initialize.
            sid = s.get("session_id")

    if not sid:
        yield s, _render_chat(history), gr.update(value=None), gr.skip(), "No audio — try again", ""
        return

    remaining = s.get("buffer", [])
    if remaining:
        try: _push(sid, _numpy_to_wav(np.concatenate(remaining), sr))
        except Exception: pass

    try: _eos(sid)
    except Exception as e:
        yield s, _render_chat(history), gr.update(value=None), gr.skip(), f"❌ {e}", ""; return

    reset_payload = _json.dumps({"reset": True, "ts": time.time()})
    yield s, _render_chat(history, partial_user="⏳  Processing…"), gr.update(value=None), reset_payload, "⏳  Processing…", "locked"

    mic_unlocked = False
    while True:
        try: session = _poll(sid)
        except Exception as e:
            yield s, _render_chat(history), gr.update(value=None), gr.skip(), f"❌ {e}", ""; return

        transcript    = str(session.get("transcript","")).strip()
        response_text = str(session.get("response","")).strip()
        segs = session.get("tts_audio_segments") or []
        running = session.get("status","") in {"running","stopping"}

        queue_upd: Any = gr.skip()
        if len(segs) > seen:
            new_urls = [_gradio_file_url(str(seg["audio_file"])) for seg in segs[seen:]]
            queue_upd = _json.dumps({"urls": new_urls, "ts": time.time()})
            seen = len(segs)

        n = len(segs)
        if n:               st = f"🔊  Speaking… ({seen}/{n})"
        elif response_text: st = "💬  Generating response…"
        elif transcript:    st = "📝  Querying knowledge base…"
        else:               st = "⏳  Processing speech…"

        lock_upd: Any = gr.skip()
        if response_text and not mic_unlocked:
            mic_unlocked = True
            lock_upd = ""

        yield s, _render_chat(history, partial_user=transcript, partial_asst=response_text), gr.skip(), queue_upd, st, lock_upd

        if not running:
            if transcript:    history.append({"role":"user",      "text": transcript})
            if response_text: history.append({"role":"assistant", "text": response_text})
            s["history"] = history; s["session_id"] = None; s["buffer"] = []; s["stream_prev"] = None
            yield s, _render_chat(history), gr.skip(), gr.skip(), "✓  Done — tap 🎤 for another question", ""
            break
        time.sleep(POLL_INTERVAL_SECONDS)

# ── KPI helpers ───────────────────────────────────────────────────────────────
_PROVIDER_LABELS = {
    "openai": "OpenAI Whisper", "openvino": "OpenVINO",
    "whispercpp": "Whisper.cpp", "pytorch": "PyTorch",
}
_DTYPE_COLORS = {"int4": "purple", "int8": "green", "fp16": "blue", "fp32": "blue"}


def _fmt_ms(val: Any) -> str:
    return f"{val:,.0f} ms" if val is not None else "—"


def _fmt_tps(val: Any) -> str:
    return f"{val:,.2f} tok/s" if val is not None else "—"


def _fmt_count(val: Any) -> str:
    return f"{int(val):,}" if val is not None else "—"


def _badge(val: str | None) -> str:
    if not val:
        return "—"
    color = _DTYPE_COLORS.get(val.lower(), "blue")
    return f'<span class="kpi-badge badge-{color}">{_esc(val.upper())}</span>'


def _kpi_row(key: str, val: str) -> str:
    return (
        f'<div class="kpi-row">'
        f'<span class="kpi-key">{key}</span>'
        f'<span class="kpi-val">{val}</span>'
        f'</div>'
    )


def _kpi_card(title: str, rows: list[tuple[str, str]]) -> str:
    inner = "\n".join(_kpi_row(k, v) for k, v in rows)
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-card-title">{title}</div>'
        f'{inner}'
        f'</div>'
    )


def _get_kpi(url: str) -> dict:
    try:
        with httpx.Client(timeout=4.0, trust_env=False) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.json()
    except Exception:
        return {}


def _fetch_kpis() -> tuple[dict, dict, dict]:
    """Return (asr_data, rag_data, tts_data) with merged model-info + latency."""
    asr_info  = _get_kpi(f"{_ANALYZER_BASE}/v1/model-info")
    asr_perf  = _get_kpi(f"{_ANALYZER_BASE}/v1/performance")
    tts_info  = _get_kpi(f"{_TTS_BASE}/v1/model-info")
    tts_perf  = _get_kpi(f"{_TTS_BASE}/v1/performance")
    rag_info  = _get_kpi(f"{_RAG_BASE}/api/v1/model-info")
    rag_perf  = _get_kpi(f"{_RAG_BASE}/api/v1/performance")
    return (
        {**asr_info, "perf": asr_perf.get("latency", {})},
        {**rag_info, "perf": rag_perf.get("latency", {})},
        {**tts_info, "perf": tts_perf.get("latency", {})},
    )


def _render_kpi_html(asr: dict, rag: dict, tts: dict) -> str:
    ap, rp, tp = asr.get("perf", {}), rag.get("perf", {}), tts.get("perf", {})

    asr_provider = _PROVIDER_LABELS.get(str(asr.get("provider", "")).lower(),
                                        asr.get("provider") or "—")
    asr_card = _kpi_card("🎤 ASR — Speech Recognition", [
        ("Model",         _esc(str(asr.get("model") or "—"))),
        ("Backend",       _esc(asr_provider)),
        ("Precision",     _badge(str(asr.get("weight_format") or "") or None)),
        ("Device",        _esc(str(asr.get("device") or "—").upper())),
        ("Last latency",  _fmt_ms(ap.get("last_ms"))),
    ])

    llm_id  = str(rag.get("llm_model") or "—")
    emb_id  = str(rag.get("embedding_model") or "—")
    rerank_id = rag.get("reranker_model") or (rag.get("reranker") or {}).get("hf_id")
    rerank_label = str(rerank_id).split("/")[-1] if rerank_id else "—"
    rp_latency = rp if isinstance(rp, dict) else {}
    rp_retrieval = rp_latency.get("retrieval") or {}
    rp_llm = rp_latency.get("llm") or {}
    rag_card = _kpi_card("🔍 RAG — Retrieval + Generation", [
        ("LLM",            _esc(llm_id.split("/")[-1])),
        ("LLM Device",     _esc(str(rag.get("llm_device") or "—"))),
        ("Precision",      _badge(str(rag.get("llm_weight_format") or "") or None)),
        ("Embeddings",     _esc(emb_id.split("/")[-1])),
        ("Emb Device",     _esc(str(rag.get("embedding_device") or "—"))),
        ("Reranker",       _esc(rerank_label)),
        ("Docs indexed",   _esc(str(rag.get("document_count") if rag.get("document_count") is not None else "—"))),
        ("Top-K",          _esc(str(rag.get("top_k") or "—"))),
        ("Retrieval lat.", _fmt_ms(rp_retrieval.get("last_ms"))),
        ("LLM lat.",       _fmt_ms(rp_llm.get("last_ms"))),
        ("TTFT", _fmt_ms(rp_llm.get("ttft_ms"))),
        ("Tokens / sec",      _fmt_tps(rp_llm.get("tokens_per_sec"))),
        ("Total tokens",      _fmt_count(rp_llm.get("total_tokens"))),
    ])

    tts_runtime = _PROVIDER_LABELS.get(str(tts.get("runtime", "")).lower(),
                                       tts.get("runtime") or "—")
    tts_model   = str(tts.get("model") or "—").split("/")[-1]
    tts_card = _kpi_card("🔊 TTS — Speech Synthesis", [
        ("Model",         _esc(tts_model)),
        ("Backend",       _esc(tts_runtime)),
        ("Precision",     _badge(str(tts.get("dtype") or "") or None)),
        ("Device",        _esc(str(tts.get("device") or "—").upper())),
        ("Language",      _esc(str(tts.get("default_language") or "—"))),
        ("Last latency",  _fmt_ms(tp.get("last_ms"))),
    ])

    return f'<div class="kpi-panel">{asr_card}{rag_card}{tts_card}</div>'


# ── Metrics / Performance helpers ────────────────────────────────────────────
def _fetch_metrics() -> dict:
    """Fetch time-series metrics via kiosk-core proxy endpoint."""
    global _LAST_METRICS_PAYLOAD
    try:
        with httpx.Client(timeout=4.0, trust_env=False) as c:
            r = c.get(f"{KIOSK_CORE_URL}/api/v1/metrics")
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict) and payload:
                _LAST_METRICS_PAYLOAD = payload
            return payload
    except Exception:
        # Keep charts moving with the latest known series during transient outages.
        return _LAST_METRICS_PAYLOAD if isinstance(_LAST_METRICS_PAYLOAD, dict) else {}


def _make_line_fig(
    series: list,
    label: str,
    color: str,
    y_max: float | None = 100,
) -> go.Figure:
    """Build a compact Plotly line figure from a [[timestamp_iso, value], ...] series."""
    xs_fmt: list[str] = []
    ys: list[float] = []
    for item in series:
        try:
            xs_fmt.append(datetime.fromisoformat(item[0]).strftime("%H:%M:%S"))
        except Exception:
            xs_fmt.append(str(item[0]))
        ys.append(float(item[1]) if len(item) > 1 else 0.0)

    rgba = color.replace("rgb(", "rgba(").replace(")", ", 0.15)")
    fig = go.Figure(
        go.Scatter(
            x=xs_fmt,
            y=ys,
            mode="lines",
            name=label,
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=rgba,
        )
    )
    fig.update_layout(
        margin=dict(l=38, r=8, t=28, b=28),
        height=185,
        title=dict(text=label, font=dict(size=11, color="#1A1A1A"), x=0.5),
        xaxis=dict(nticks=6, tickangle=0, tickfont=dict(size=9)),
        yaxis=dict(
            title="%",
            titlefont=dict(size=9),
            tickfont=dict(size=9),
            range=[0, y_max] if y_max is not None else None,
            rangemode="tozero" if y_max is None else "normal",
        ),
        plot_bgcolor="#F4F7FB",
        paper_bgcolor="#FFFFFF",
        showlegend=False,
    )
    if not ys:
        fig.add_annotation(
            text="Waiting for data\u2026",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=11, color="#8FA0AE"),
        )
    return fig


def _fetch_performance_charts() -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    """Return four Plotly figures: cpu, gpu, memory, npu."""
    metrics = _fetch_metrics()
    cpu_fig = _make_line_fig(
        metrics.get("cpu_utilization", []),
        "CPU Utilization", "rgb(54, 162, 235)",
    )
    gpu_fig = _make_line_fig(
        metrics.get("gpu_utilization", []),
        "GPU Utilization", "rgb(75, 192, 192)",
    )
    # memory items: [ts, total_gb, used_gb, free_gb, usage_pct]
    mem_raw = metrics.get("memory", [])
    mem_series = [[item[0], item[4]] for item in mem_raw if len(item) > 4]
    mem_fig = _make_line_fig(mem_series, "Memory Utilization", "rgb(255, 99, 132)")
    npu_fig = _make_line_fig(
        metrics.get("npu_utilization", []),
        "NPU Utilization", "rgb(153, 102, 255)",
    )
    return cpu_fig, gpu_fig, mem_fig, npu_fig


# ── App ───────────────────────────────────────────────────────────────────────
def create_app() -> gr.Blocks:
    with gr.Blocks(title="Kiosk Voice Assistant") as app:
        state = gr.State(dict(_INIT))

        gr.Markdown("## 🎙 Kiosk Voice Assistant")

        with gr.Row(elem_classes=["kiosk-row"]):

            # ── Left: chat + mic ──────────────────────────────────────────────
            with gr.Column(elem_classes=["kiosk-left"]):
                chat   = gr.HTML(value=_render_chat([]))
                with gr.Row(elem_classes=["status-row"]):
                    status = gr.HTML(value='<div class="status-line">Tap the mic and ask a question</div>')
                    with gr.Column(scale=0, min_width=180, elem_classes=["status-tts-col"]):
                        tts = gr.Audio(
                            label="🗣️ Assistant",
                            interactive=False,
                            autoplay=False,
                            elem_id="kiosk-tts",
                        )
                        tts_queue = gr.Textbox(
                            value="",
                            visible=False,
                            elem_id="kiosk-tts-queue",
                        )
                        mic_lock = gr.Textbox(
                            value="",
                            visible=False,
                            elem_id="kiosk-mic-lock",
                        )
                with gr.Row(elem_classes=["audio-pair"]):
                    mic = gr.Audio(
                        sources=["microphone"],
                        type="numpy",
                        streaming=True,
                        label="🎤 Your Voice",
                        elem_id="kiosk-mic",
                    )

            # ── Right: collapsible panels ────────────────────────────────────
            with gr.Column(elem_classes=["kiosk-right"]):
                with gr.Accordion(label="🎤 Device Settings", open=False):
                    gr.HTML(value='<div id="mic-device-panel"><p class="ingest-note">Select the microphone to use for recording.</p></div>')

                with gr.Accordion(label="📚 Update Knowledge Base", open=False):
                    gr.HTML(value=_INGEST_NOTE_HTML)
                    sample_choice = gr.Radio(
                        choices=list(_SAMPLE_KB_OPTIONS.keys()),
                        value=_DEFAULT_SAMPLE_KB,
                        label="Use a built-in sample knowledge base",
                    )
                    sample_download = gr.File(
                        value=_sample_download_value(_DEFAULT_SAMPLE_KB),
                        label="Download selected sample",
                        interactive=False,
                    )
                    sample_ingest_btn = gr.Button("Use Sample & Ingest", variant="secondary", size="sm")
                    ingest_btn = gr.UploadButton(
                        "📄 Upload .txt / .md & Ingest",
                        file_types=[".txt", ".md"],
                        file_count="single",
                        variant="primary",
                        size="sm",
                    )
                    ingest_status = gr.HTML(value="")

                with gr.Accordion(label="📈 Performance", open=True):
                    perf_timer = gr.Timer(value=PERF_REFRESH_SECONDS, active=True)
                    cpu_plot = gr.Plot(label="CPU", show_label=False)
                    gpu_plot = gr.Plot(label="GPU", show_label=False)
                    mem_plot = gr.Plot(label="Memory", show_label=False)
                    npu_plot = gr.Plot(label="NPU", show_label=False)
                    perf_refresh_btn = gr.Button("🔄 Refresh", size="sm", variant="secondary")

                with gr.Accordion(label="📊 Model KPIs", open=True):
                    kpi_panel = gr.HTML(value=_render_kpi_html({}, {}, {}))
                    refresh_btn = gr.Button("🔄 Refresh", size="sm", variant="secondary")
                    # Hidden trigger clicked from JS after the first TTS wav
                    # starts playing (and again after the last one ends), so
                    # KPIs auto-refresh once a full user-question -> spoken-answer
                    # cycle completes. Kept in the DOM via CSS class so the JS
                    # .click() reliably reaches Gradio's event handler.
                    kpi_auto_refresh_btn = gr.Button(
                        "auto-refresh",
                        elem_id="kpi-auto-refresh-trigger",
                        elem_classes=["kiosk-hidden"],
                    )

        outs = [state, chat, tts, tts_queue, status, mic_lock]

        mic.start_recording(fn=on_start, inputs=[state],         outputs=outs)
        mic.stream(         fn=on_chunk, inputs=[state, mic],    outputs=outs, stream_every=0.5)
        mic.stop_recording( fn=on_stop,  inputs=[state, mic],    outputs=outs)

        tts_queue.change(
            fn=None,
            inputs=[tts_queue],
            js="(payload) => { if (window.kioskTTSEnqueue) window.kioskTTSEnqueue(payload); }",
        )
        mic_lock.change(
            fn=None,
            inputs=[mic_lock],
            js="""(val) => {
                const container = document.querySelector('.gradio-container');
                if (!container) return;
                if (val && val.trim() !== '') {
                    container.classList.add('kiosk-mic-locked');
                } else {
                    container.classList.remove('kiosk-mic-locked');
                }
            }""",
        )

        _perf_plots = [cpu_plot, gpu_plot, mem_plot, npu_plot]
        perf_refresh_btn.click(
            fn=_fetch_performance_charts,
            outputs=_perf_plots,
        )
        perf_timer.tick(
            fn=_fetch_performance_charts,
            outputs=_perf_plots,
        )

        refresh_btn.click(
            fn=lambda: _render_kpi_html(*_fetch_kpis()),
            outputs=[kpi_panel],
        )
        kpi_auto_refresh_btn.click(
            fn=lambda: _render_kpi_html(*_fetch_kpis()),
            outputs=[kpi_panel],
        )
        ingest_btn.upload(
            fn=_ingest_doc,
            inputs=[ingest_btn],
            outputs=[ingest_status, ingest_btn, sample_ingest_btn],
        )
        sample_choice.change(
            fn=_sample_download_value,
            inputs=[sample_choice],
            outputs=[sample_download],
        )
        sample_ingest_btn.click(
            fn=_ingest_sample_doc,
            inputs=[sample_choice],
            outputs=[ingest_status, ingest_btn, sample_ingest_btn],
        )
        app.load(
            fn=_fetch_performance_charts,
            outputs=_perf_plots,
        )
        app.load(
            fn=lambda: _render_kpi_html(*_fetch_kpis()),
            outputs=[kpi_panel],
        )
        app.load(
            fn=None,
            js="""() => {
                if (!window.kioskTTS) {
                    window.kioskTTS = { queue: [], played: new Set(), playing: false, player: null, host: null, indicator: null };
                }
                const setTTSVisualState = (mode) => {
                    const state = window.kioskTTS;
                    const host = state.host || document.querySelector('#kiosk-tts');
                    if (!host) return;
                    state.host = host;
                    host.classList.remove('kiosk-tts-idle', 'kiosk-tts-queued', 'kiosk-tts-playing');
                    host.classList.add(mode || 'kiosk-tts-idle');
                };
                const ensureTTSPlayer = () => {
                    const host = document.querySelector('#kiosk-tts');
                    if (!host) return null;
                    window.kioskTTS.host = host;
                    let indicator = host.querySelector('.kiosk-tts-indicator');
                    if (!indicator) {
                        indicator = document.createElement('div');
                        indicator.className = 'kiosk-tts-indicator';
                        indicator.innerHTML = `
                            <div class="kiosk-tts-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                                    <path d="M3 10v4c0 .55.45 1 1 1h3l5 4V5L7 9H4c-.55 0-1 .45-1 1zm12.5 2c0-1.77-1-3.29-2.5-4.03v8.05A4.47 4.47 0 0 0 15.5 12zm0-9.5v2.06c2.89.86 5 3.54 5 6.44s-2.11 5.58-5 6.44v2.06c4.01-.91 7-4.49 7-8.5s-2.99-7.59-7-8.5z"/>
                                </svg>
                            </div>
                            <div class="kiosk-tts-title">Kiosk Assist</div>
                            <div class="kiosk-tts-subtitle"></div>
                            <div class="kiosk-tts-bars" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
                        `;
                        const target = host.querySelector('.block') || host;
                        target.appendChild(indicator);
                    }
                    window.kioskTTS.indicator = indicator;
                    let player = host.querySelector('audio');
                    if (!player) {
                        player = document.createElement('audio');
                        player.controls = false;
                        player.preload = 'auto';
                        player.style.display = 'none';
                        const target = host.querySelector('.block') || host;
                        target.appendChild(player);
                    }
                    if (!player.dataset.kioskBound) {
                        player.addEventListener('play', () => {
                            // Fire as soon as the first wav of this answer cycle
                            // starts playing. ASR/RAG metrics are already final
                            // by this point; TTS last_ms will reflect at least the
                            // first chunk. The 'ended' handler below will refresh
                            // again once the queue fully drains.
                            if (!window.kioskTTS.refreshedOnPlay) {
                                window.kioskTTS.refreshedOnPlay = true;
                                window.kioskTriggerKpiRefresh && window.kioskTriggerKpiRefresh();
                            }
                        });
                        player.addEventListener('ended', () => {
                            window.kioskTTS.playing = false;
                            setTTSVisualState(window.kioskTTS.queue.length > 0 ? 'kiosk-tts-queued' : 'kiosk-tts-idle');
                            if (window.kioskTTS.queue.length === 0) {
                                window.kioskTriggerKpiRefresh && window.kioskTriggerKpiRefresh();
                            }
                            window.kioskTTSPlayNext();
                        });
                        player.addEventListener('error', () => {
                            window.kioskTTS.playing = false;
                            setTTSVisualState(window.kioskTTS.queue.length > 0 ? 'kiosk-tts-queued' : 'kiosk-tts-idle');
                            window.kioskTTSPlayNext();
                        });
                        player.dataset.kioskBound = '1';
                    }
                    window.kioskTTS.player = player;
                    setTTSVisualState(window.kioskTTS.playing ? 'kiosk-tts-playing' : (window.kioskTTS.queue.length > 0 ? 'kiosk-tts-queued' : 'kiosk-tts-idle'));
                    return player;
                };
                window.kioskTTSPlayNext = () => {
                    const state = window.kioskTTS;
                    const player = ensureTTSPlayer();
                    if (!player) {
                        state.playing = false;
                        setTTSVisualState('kiosk-tts-idle');
                        setTimeout(window.kioskTTSPlayNext, 150);
                        return;
                    }
                    if (state.queue.length === 0) {
                        state.playing = false;
                        setTTSVisualState('kiosk-tts-idle');
                        return;
                    }
                    state.playing = true;
                    setTTSVisualState('kiosk-tts-playing');
                    const nextUrl = state.queue.shift();
                    player.src = nextUrl;
                    player.load();
                    const pending = player.play();
                    if (pending && typeof pending.catch === 'function') {
                        pending.catch(() => {
                            state.playing = false;
                            setTTSVisualState(state.queue.length > 0 ? 'kiosk-tts-queued' : 'kiosk-tts-idle');
                            setTimeout(window.kioskTTSPlayNext, 150);
                        });
                    }
                };
                window.kioskTTSEnqueue = (payload) => {
                    if (!payload) return;
                    let data = null;
                    try { data = JSON.parse(payload); } catch (e) { return; }
                    if (!data) return;
                    const state = window.kioskTTS;
                    ensureTTSPlayer();
                    if (data.reset) {
                        state.queue = [];
                        state.played.clear();
                        state.playing = false;
                        state.refreshedOnPlay = false;
                        if (state.player) {
                            state.player.pause();
                            state.player.removeAttribute('src');
                            state.player.load();
                        }
                        setTTSVisualState('kiosk-tts-idle');
                        return;
                    }
                    const urls = Array.isArray(data.urls) ? data.urls : [];
                    let appended = 0;
                    for (const url of urls) {
                        if (!url || state.played.has(url)) continue;
                        state.played.add(url);
                        state.queue.push(url);
                        appended += 1;
                    }
                    // New wavs arriving after a previous cycle finished should
                    // count as a fresh answer cycle for the first-wav refresh.
                    if (appended > 0 && !state.playing && state.queue.length === appended) {
                        state.refreshedOnPlay = false;
                    }
                    if (!state.playing && state.queue.length > 0) {
                        setTTSVisualState('kiosk-tts-queued');
                    }
                    if (!state.playing && state.queue.length > 0) {
                        window.kioskTTSPlayNext();
                    }
                };
                ensureTTSPlayer();

                // Click the hidden Gradio button so the server re-fetches and
                // re-renders the KPI panel. Debounced so a flurry of "ended" /
                // "play" events (one per wav) only triggers a single refresh.
                window.kioskTriggerKpiRefresh = () => {
                    if (window.kioskTTS.kpiRefreshTimer) {
                        clearTimeout(window.kioskTTS.kpiRefreshTimer);
                    }
                    window.kioskTTS.kpiRefreshTimer = setTimeout(() => {
                        const host = document.getElementById('kpi-auto-refresh-trigger');
                        const btn = host ? (host.querySelector('button') || (host.tagName === 'BUTTON' ? host : null)) : null;
                        if (btn) {
                            btn.click();
                            console.debug('[kiosk] KPI auto-refresh fired');
                        } else {
                            console.warn('[kiosk] KPI auto-refresh trigger button not found in DOM');
                        }
                    }, 250);
                };

                // Rename "Record" button to "Ask"
                const renameRecord = () => {
                    document.querySelectorAll('#kiosk-mic button').forEach(btn => {
                        btn.childNodes.forEach(node => {
                            if (node.nodeType === Node.TEXT_NODE &&
                                    node.textContent.trim().toLowerCase() === 'record') {
                                node.textContent = node.textContent.replace(/record/i, 'Ask');
                            }
                        });
                        const span = btn.querySelector('span');
                        if (span && span.textContent.trim().toLowerCase() === 'record') {
                            span.textContent = 'Ask';
                        }
                    });
                };

                // Teleport the Stop button out of the recorder container so
                // Svelte's internal re-renders never touch our layout. The
                // recorder container itself is moved into #kiosk-recorder-bin
                // attached to <body>, far away from the speak-button slot.
                const ensureStopHost = () => {
                    const block = document.querySelector('#kiosk-mic .block') || document.querySelector('#kiosk-mic');
                    if (!block) return null;
                    let host = block.querySelector(':scope > .kiosk-stop-host');
                    if (!host) {
                        host = document.createElement('div');
                        host.className = 'kiosk-stop-host';
                        block.appendChild(host);
                    }
                    return host;
                };
                const ensureRecorderBin = () => {
                    let bin = document.getElementById('kiosk-recorder-bin');
                    if (!bin) {
                        bin = document.createElement('div');
                        bin.id = 'kiosk-recorder-bin';
                        document.body.appendChild(bin);
                    }
                    return bin;
                };
                const isStopButton = (btn) => {
                    if (!btn) return false;
                    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const title = (btn.getAttribute('title') || '').toLowerCase();
                    const text = (btn.textContent || '').trim().toLowerCase();
                    if (aria.includes('stop')) return true;
                    if (title.includes('stop')) return true;
                    if (text === 'stop') return true;
                    return false;
                };
                // Walk up from `node` until we find a child of #kiosk-mic .block
                // — that's the recorder root we want to move.
                const findRecorderRoot = (node) => {
                    const block = document.querySelector('#kiosk-mic .block');
                    if (!block || !node) return null;
                    let cur = node;
                    while (cur && cur.parentElement && cur.parentElement !== block) {
                        cur = cur.parentElement;
                        if (!block.contains(cur)) return null;
                    }
                    return cur && cur.parentElement === block ? cur : null;
                };
                const teleportRecorder = () => {
                    const mic = document.querySelector('#kiosk-mic');
                    if (!mic) return;
                    const host = ensureStopHost();
                    if (!host) return;
                    const bin = ensureRecorderBin();

                    // First: hoist the Stop button into our host (if recorder
                    // is still inside the mic block — happens for an instant
                    // before we teleport it).
                    mic.querySelectorAll('button').forEach((b) => {
                        if (isStopButton(b) && b.parentElement !== host) {
                            b.removeAttribute('style');
                            host.appendChild(b);
                        }
                    });
                    // Also catch any stop button that rode along into the bin
                    bin.querySelectorAll('button').forEach((b) => {
                        if (isStopButton(b) && b.parentElement !== host) {
                            b.removeAttribute('style');
                            host.appendChild(b);
                        }
                    });

                    // Recording is "active" iff the mic has any <canvas>
                    // (live waveform) inside it. If so, teleport its root.
                    const canvas = mic.querySelector('canvas');
                    if (canvas) {
                        const root = findRecorderRoot(canvas);
                        if (root && root.parentElement !== bin) {
                            // Strip inline positioning Svelte applied
                            root.removeAttribute('style');
                            bin.appendChild(root);
                        }
                    } else if (bin.childElementCount === 0) {
                        // No recording and bin empty — nothing to do.
                    }
                };

                const moveSelect = () => {
                    const sel = document.querySelector('#kiosk-mic select');
                    const tgt = document.querySelector('#mic-device-panel');
                    if (sel && tgt && !tgt.contains(sel)) {
                        // Strip any inline width/size styles so CSS 100% takes over
                        sel.removeAttribute('style');
                        sel.style.width = '100%';
                        sel.style.boxSizing = 'border-box';
                        tgt.appendChild(sel);
                        return true;
                    }
                    return !!(sel && tgt);
                };
                const scrollChatToBottom = () => {
                    const pane = document.querySelector('.chat-pane');
                    if (!pane) return;
                    const anchor = pane.querySelector('.chat-end-anchor');
                    if (anchor) {
                        anchor.scrollIntoView({ block: 'end', behavior: 'smooth' });
                    }
                    pane.scrollTop = pane.scrollHeight;
                };
                // Retry every 400 ms for up to 15 s (Svelte renders lazily).
                let tries = 0;
                const poll = setInterval(() => {
                    renameRecord();
                    teleportRecorder();
                    scrollChatToBottom();
                    if (moveSelect() || ++tries > 37) clearInterval(poll);
                }, 400);
                // Re-run whenever DOM changes (accordion open, Gradio re-render)
                const obs = new MutationObserver(() => {
                    moveSelect();
                    renameRecord();
                    teleportRecorder();
                    requestAnimationFrame(scrollChatToBottom);
                });
                obs.observe(document.body, { childList: true, subtree: true });
                requestAnimationFrame(scrollChatToBottom);
            }""",
        )

    return app

def launch_app() -> Any:
    # Allow Gradio to serve TTS audio files generated by kiosk-core
    _generated_audio = os.path.join(
        os.path.dirname(__file__), "generated_audio"
    )
    os.makedirs(_generated_audio, exist_ok=True)
    return create_app().launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=STYLE,
        allowed_paths=[_generated_audio],
    )

if __name__ == "__main__":
    launch_app()
