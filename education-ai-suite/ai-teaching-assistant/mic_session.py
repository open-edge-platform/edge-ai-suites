"""
CLI interface for the smart-kiosk-assistant microphone pipeline.

Default mode — interactive loop
────────────────────────────────
Run without flags to enter the interactive loop:

    python mic_session.py

The loop works like this:
  1. "Press ENTER to speak (Ctrl+C to quit)..." is printed.
  2. User presses Enter → mic opens immediately.
  3. Speak your question. The mic stops automatically after
     silence_timeout_seconds of quiet following detected speech,
     or after max_session_seconds total.
  4. Transcript → RAG response → TTS clip paths are printed to the terminal.
  5. Back to step 1 for the next question.

Press Ctrl+C at the prompt to exit cleanly.
Press Ctrl+C while recording to stop the current session early.

One-shot mode
─────────────
    python mic_session.py --one-shot    # single session then exit

Other options
─────────────
    python mic_session.py --list-devices
    python mic_session.py --device 0 --silence-threshold 700
"""

from __future__ import annotations

import argparse
import signal
import sys
import time

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Interactive CLI for the smart-kiosk-assistant mic pipeline. "
            "By default runs in a loop: press Enter to speak, see results, repeat."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8012", help="kiosk-core base URL")
    parser.add_argument("--list-devices", action="store_true", help="Print available input devices and exit")
    parser.add_argument("--one-shot", action="store_true",
                        help="Run a single session then exit instead of looping")
    parser.add_argument("--device", default=None,
                        help="Input device index or name. Use 'default' or 'pipewire' for software resampling.")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--chunk-seconds", type=float, default=4.0)
    parser.add_argument("--silence-timeout-seconds", type=float, default=1.5,
                        help="Seconds of silence after speech that ends the session")
    parser.add_argument("--max-session-seconds", type=float, default=20.0)
    parser.add_argument("--silence-threshold", type=int, default=900,
                        help="RMS threshold for speech detection (lower = more sensitive)")
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
# API helpers
# ─────────────────────────────────────────────────────────────────────────────

def list_devices(client: httpx.Client, base_url: str) -> None:
    response = client.get(f"{base_url}/api/v1/devices")
    response.raise_for_status()
    devices = response.json().get("devices", [])
    if not devices:
        print("No input devices found.")
        return
    print("Available input devices:")
    for d in devices:
        print(f"  [{d['id']}] {d['name']}  (default_samplerate={d['default_samplerate']})")


def start_session(client: httpx.Client, args: argparse.Namespace) -> dict:
    payload: dict = {
        "sample_rate": args.sample_rate,
        "chunk_seconds": args.chunk_seconds,
        "silence_timeout_seconds": args.silence_timeout_seconds,
        "max_session_seconds": args.max_session_seconds,
        "silence_threshold": args.silence_threshold,
        "language": args.language,
        "temperature": args.temperature,
        "tts_model": args.tts_model,
        "tts_language": args.tts_language,
    }
    if args.device is not None:
        try:
            payload["device"] = int(args.device)
        except ValueError:
            payload["device"] = args.device
    if args.analyzer_url:
        payload["analyzer_url"] = args.analyzer_url
    if args.rag_url:
        payload["rag_url"] = args.rag_url
    if args.tts_url:
        payload["tts_url"] = args.tts_url
    if args.tts_voice:
        payload["tts_voice"] = args.tts_voice
    if args.tts_instructions:
        payload["tts_instructions"] = args.tts_instructions

    response = client.post(f"{args.base_url}/api/v1/sessions/start", json=payload)
    response.raise_for_status()
    return response.json()


def stop_session(client: httpx.Client, base_url: str, session_id: str) -> None:
    try:
        client.post(f"{base_url}/api/v1/sessions/{session_id}/stop")
    except Exception:
        pass


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
            label = "listening..." if not speech_started else f"captured {captured:.1f}s | chunks: {parts}"
            print(f"\r  [{payload['status']}] {label}", end="", flush=True)
            previous_captured = captured
            previous_parts = parts

        response_text = payload.get("response", "") or ""
        if response_text.startswith(previous_response) and len(response_text) > len(previous_response):
            if not response_header_printed:
                print("\n\n  Assistant:\n")
                response_header_printed = True
            print(f"  {response_text[len(previous_response):]}", end="", flush=True)
            previous_response = response_text

        tts_segments = payload.get("tts_audio_segments", [])
        if len(tts_segments) > previous_tts:
            for seg in tts_segments[previous_tts:]:
                print(f"\n  [TTS] {seg['audio_file']}")
                print(f"        \"{seg['text']}\"")
            previous_tts = len(tts_segments)

        if payload["status"] not in {"running", "stopping"}:
            if response_header_printed:
                print()
            return payload

        time.sleep(args.poll_interval)

    raise TimeoutError(f"Session {session_id} timed out after {args.max_polls} polls.")


def print_result(result: dict) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    if result.get("error"):
        print(f"  Error     : {result['error']}")

    transcript = (result.get("transcript") or "").strip()
    if transcript:
        print(f"  You said  : {transcript}")

    tts_segments = result.get("tts_audio_segments", [])
    if tts_segments:
        print(f"\n  Play response with aplay:")
        for seg in tts_segments:
            print(f"    aplay \"{seg['audio_file']}\"")

    tts_errors = result.get("tts_errors", [])
    if tts_errors:
        print(f"\n  TTS errors: {tts_errors}")

    if not transcript and not tts_segments and not result.get("error"):
        print("  No speech detected.")

    print(sep)


# ─────────────────────────────────────────────────────────────────────────────
# Session runner
# ─────────────────────────────────────────────────────────────────────────────

def run_one_session(client: httpx.Client, args: argparse.Namespace) -> bool:
    """
    Start a single mic session and poll until done.
    Returns True if completed successfully, False on error.
    Ctrl+C during recording triggers a clean stop of this session only.
    """
    try:
        started = start_session(client, args)
    except Exception as exc:
        print(f"  Failed to start session: {exc}", file=sys.stderr)
        return False

    session_id = started["session_id"]
    print(f"  Mic is open. Speak now.")
    print(f"  Auto-stops after {args.silence_timeout_seconds}s silence "
          f"or {args.max_session_seconds}s total. Ctrl+C to stop early.\n")

    interrupted = False

    original_sigint = signal.getsignal(signal.SIGINT)

    def _stop_this_session(sig, frame):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            print("\n  Stopping recording...", flush=True)
            stop_session(client, args.base_url, session_id)

    signal.signal(signal.SIGINT, _stop_this_session)

    success = True
    try:
        result = poll_until_done(client, args, session_id)
        print_result(result)
        success = result["status"] == "completed"
    except TimeoutError as exc:
        print(f"\n  {exc}", file=sys.stderr)
        stop_session(client, args.base_url, session_id)
        success = False
    except Exception as exc:
        print(f"\n  Polling error: {exc}", file=sys.stderr)
        success = False
    finally:
        # Restore the outer signal handler (handles Ctrl+C at the prompt)
        signal.signal(signal.SIGINT, original_sigint)

    return success


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    with httpx.Client(trust_env=False, timeout=args.request_timeout) as client:
        try:
            client.get(f"{args.base_url}/health").raise_for_status()
        except Exception as exc:
            print(f"kiosk-core not reachable at {args.base_url}: {exc}", file=sys.stderr)
            return 1

        if args.list_devices:
            list_devices(client, args.base_url)
            return 0

        # ── Header ──────────────────────────────────────────────────────────
        print("╔══════════════════════════════════════════════╗")
        print("║       Smart Kiosk Assistant — Mic CLI        ║")
        print("╚══════════════════════════════════════════════╝")
        print(f"  kiosk-core : {args.base_url}")
        device_label = args.device if args.device is not None else "default"
        print(f"  device     : {device_label}  |  {args.sample_rate}Hz")
        print(f"  silence    : {args.silence_timeout_seconds}s timeout  |  "
              f"threshold {args.silence_threshold}")
        print()

        if args.one_shot:
            print("  Press ENTER to speak...")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return 0
            run_one_session(client, args)
            return 0

        # ── Interactive loop ─────────────────────────────────────────────────
        turn = 0
        while True:
            turn += 1
            print(f"\n  ┌─ Turn {turn} " + "─" * max(0, 44 - len(str(turn))) + "┐")
            try:
                print("  │  Press ENTER to speak  (Ctrl+C to quit)         │")
                print("  └" + "─" * 50 + "┘")
                input()
            except (EOFError, KeyboardInterrupt):
                print("\n\nBye.")
                return 0

            run_one_session(client, args)


if __name__ == "__main__":
    raise SystemExit(main())

