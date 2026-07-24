"""
virtual_mic_session.py — Simulates a live microphone session using a WAV file.

Feeds the WAV through kiosk-core at real-time speed (realtime_factor=1.0 by
default), exercising the identical pipeline as a real mic: chunking, silence
detection, ASR → RAG → TTS.

Use --loop to keep replaying the file (useful for sustained pipeline testing).
Use --realtime-factor < 1.0 to slow down (simulate slow speaker).
Use --realtime-factor > 1.0 to speed up (faster than real time).

Usage examples
──────────────
# Single pass, real-time
python virtual_mic_session.py question.wav

# Loop 3 times (ask the same question 3 times end-to-end)
python virtual_mic_session.py question.wav --loop 3

# Point at a non-default kiosk-core
python virtual_mic_session.py question.wav --base-url http://192.168.1.5:8012

# All overrides
python virtual_mic_session.py question.wav \\
  --base-url http://127.0.0.1:8012 \\
  --silence-timeout-seconds 1.5 \\
  --max-session-seconds 20 \\
  --silence-threshold 900 \\
  --realtime-factor 1.0 \\
  --loop 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import wave
from pathlib import Path

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate a live mic session using a WAV file fed through kiosk-core in real time."
    )
    parser.add_argument("audio_file", help="Path to a 16-bit mono PCM WAV file")
    parser.add_argument("--base-url", default="http://127.0.0.1:8012")
    parser.add_argument("--loop", type=int, default=1, metavar="N",
                        help="Number of times to replay the file (default: 1). Use 0 for infinite.")
    parser.add_argument("--realtime-factor", type=float, default=1.0,
                        help="1.0 = real time. >1 = faster. <1 = slower. (default: 1.0)")
    parser.add_argument("--chunk-seconds", type=float, default=4.0)
    parser.add_argument("--silence-timeout-seconds", type=float, default=1.5)
    parser.add_argument("--max-session-seconds", type=float, default=20.0)
    parser.add_argument("--silence-threshold", type=int, default=900)
    parser.add_argument("--language", default="en")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--analyzer-url", default=None)
    parser.add_argument("--rag-url", default=None)
    parser.add_argument("--tts-url", default=None)
    parser.add_argument("--tts-model", default="qwen-tts")
    parser.add_argument("--tts-voice", default=None)
    parser.add_argument("--tts-language", default="English")
    parser.add_argument("--tts-instructions", default=None)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--max-polls", type=int, default=360)
    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_wav_info(path: str) -> tuple[int, float]:
    """Return (sample_rate, duration_seconds)."""
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        frames = w.getnframes()
        bits = w.getsampwidth() * 8
        chans = w.getnchannels()
    if bits != 16:
        raise ValueError(f"Only 16-bit PCM WAV is supported (got {bits}-bit)")
    return rate, frames / rate


def start_file_session(client: httpx.Client, args: argparse.Namespace, sample_rate: int) -> dict:
    audio_path = Path(args.audio_file)
    data: dict = {
        "sample_rate": str(sample_rate),
        "chunk_seconds": str(args.chunk_seconds),
        "silence_timeout_seconds": str(args.silence_timeout_seconds),
        "max_session_seconds": str(args.max_session_seconds),
        "silence_threshold": str(args.silence_threshold),
        "language": args.language,
        "temperature": str(args.temperature),
        "realtime_factor": str(args.realtime_factor),
        "tts_model": args.tts_model,
        "tts_language": args.tts_language,
    }
    if args.analyzer_url:
        data["analyzer_url"] = args.analyzer_url
    if args.rag_url:
        data["rag_url"] = args.rag_url
    if args.tts_url:
        data["tts_url"] = args.tts_url
    if args.tts_voice:
        data["tts_voice"] = args.tts_voice
    if args.tts_instructions:
        data["tts_instructions"] = args.tts_instructions

    with audio_path.open("rb") as f:
        resp = client.post(
            f"{args.base_url}/api/v1/sessions/start-file",
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
        )
    resp.raise_for_status()
    return resp.json()


def poll_until_done(client: httpx.Client, args: argparse.Namespace, session_id: str) -> dict:
    previous_captured = None
    previous_parts = 0
    previous_response = ""
    response_header_printed = False
    previous_tts = 0

    for _ in range(args.max_polls):
        resp = client.get(f"{args.base_url}/api/v1/sessions/{session_id}")
        resp.raise_for_status()
        payload = resp.json()

        captured = payload.get("captured_audio_seconds")
        parts = len(payload.get("transcript_parts", []))
        speech_started = payload.get("speech_started", False)

        if captured != previous_captured or parts != previous_parts:
            label = "feeding audio..." if not speech_started else f"captured {captured:.1f}s | chunks: {parts}"
            print(f"\r[{payload['status']}] {label}", end="", flush=True)
            previous_captured = captured
            previous_parts = parts

        response_text = payload.get("response", "") or ""
        if response_text.startswith(previous_response) and len(response_text) > len(previous_response):
            if not response_header_printed:
                print("\n\nRAG response:\n")
                response_header_printed = True
            print(response_text[len(previous_response):], end="", flush=True)
            previous_response = response_text

        tts_segments = payload.get("tts_audio_segments", [])
        if len(tts_segments) > previous_tts:
            for seg in tts_segments[previous_tts:]:
                print(f"\n[TTS ready] {seg['audio_file']}")
                print(f"            \"{seg['text']}\"")
            previous_tts = len(tts_segments)

        if payload["status"] not in {"running", "stopping"}:
            if response_header_printed:
                print()
            return payload

        time.sleep(args.poll_interval)

    raise TimeoutError(f"Session {session_id} did not finish after {args.max_polls} polls")


def print_summary(result: dict, run_index: int, total: int) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    if total > 1:
        print(f"Run {run_index}/{total}")
    print(f"Status    : {result['status']}")
    print(f"End reason: {result.get('end_reason')}")
    if result.get("error"):
        print(f"Error     : {result['error']}")

    transcript = (result.get("transcript") or "").strip()
    if transcript:
        print(f"\nTranscript:\n  {transcript}")

    tts_segments = result.get("tts_audio_segments", [])
    if tts_segments:
        print(f"\nTTS audio clips — play with: aplay <path>")
        for seg in tts_segments:
            print(f"  [{seg['index']}] {seg['audio_file']}")
            print(f"       \"{seg['text']}\"")
    else:
        print("\nNo TTS audio generated (no speech detected or RAG/TTS error).")

    tts_errors = result.get("tts_errors", [])
    if tts_errors:
        print(f"\nTTS errors: {tts_errors}")
    print(sep)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    audio_path = Path(args.audio_file)
    if not audio_path.is_file():
        print(f"File not found: {audio_path}", file=sys.stderr)
        return 1

    try:
        sample_rate, duration = read_wav_info(str(audio_path))
    except Exception as exc:
        print(f"Cannot read WAV: {exc}", file=sys.stderr)
        return 1

    expected_wall = duration / args.realtime_factor
    print(f"File      : {audio_path.name}  ({duration:.1f}s, {sample_rate}Hz)")
    print(f"Realtime  : factor={args.realtime_factor}  (~{expected_wall:.1f}s wall time per pass)")
    print(f"Pipeline  : chunk={args.chunk_seconds}s  silence_timeout={args.silence_timeout_seconds}s  "
          f"max={args.max_session_seconds}s  threshold={args.silence_threshold}")

    total_runs = args.loop if args.loop > 0 else float("inf")
    run = 0
    exit_code = 0

    with httpx.Client(trust_env=False, timeout=args.request_timeout) as client:
        # Health check
        try:
            client.get(f"{args.base_url}/health").raise_for_status()
            print(f"kiosk-core : {args.base_url}  ✓\n")
        except Exception as exc:
            print(f"kiosk-core not reachable at {args.base_url}: {exc}", file=sys.stderr)
            return 1

        while run < total_runs:
            run += 1
            label = f"[Pass {run}]" if (args.loop != 1) else ""
            print(f"{label} Starting virtual mic session...".strip())

            try:
                started = start_file_session(client, args, sample_rate)
            except Exception as exc:
                print(f"Failed to start session: {exc}", file=sys.stderr)
                return 1

            session_id = started["session_id"]
            print(f"session_id : {session_id}")

            try:
                result = poll_until_done(client, args, session_id)
            except TimeoutError as exc:
                print(f"\n{exc}", file=sys.stderr)
                exit_code = 1
                break
            except Exception as exc:
                print(f"\nPolling error: {exc}", file=sys.stderr)
                exit_code = 1
                break

            print_summary(result, run, args.loop if args.loop > 0 else run)

            if result["status"] != "completed":
                exit_code = 1

            if run < total_runs:
                print(f"\nWaiting 2s before next pass...\n")
                time.sleep(2)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
