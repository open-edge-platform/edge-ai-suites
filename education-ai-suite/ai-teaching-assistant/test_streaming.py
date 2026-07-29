import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay an audio file through kiosk-core's file-backed session endpoint "
            "to exercise the same chunking and analyzer transcription flow as microphone capture."
        )
    )
    parser.add_argument("audio_file", help="Path to a 16-bit PCM WAV file")
    parser.add_argument("--base-url", default="http://127.0.0.1:8012", help="kiosk-core base URL")
    parser.add_argument(
        "--start-endpoint",
        default="/api/v1/sessions/start-file",
        help="Session start endpoint for file-backed testing",
    )
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--chunk-seconds", type=float, default=4.0)
    parser.add_argument("--silence-timeout-seconds", type=float, default=1.5)
    parser.add_argument("--max-session-seconds", type=float, default=12.0)
    parser.add_argument("--silence-threshold", type=int, default=900)
    parser.add_argument("--language", default="en")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--realtime-factor", type=float, default=20.0)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--max-polls", type=int, default=180)
    parser.add_argument(
        "--analyzer-url",
        default=None,
        help="Optional override for the downstream analyzer transcription endpoint",
    )
    parser.add_argument(
        "--rag-url",
        default=None,
        help="Optional override for the downstream RAG streaming query endpoint",
    )
    parser.add_argument(
        "--tts-url",
        default=None,
        help="Optional override for the downstream TTS endpoint used for sentence audio generation",
    )
    parser.add_argument("--tts-model", default="qwen-tts")
    parser.add_argument("--tts-voice", default=None)
    parser.add_argument("--tts-language", default="English")
    parser.add_argument("--tts-instructions", default=None)
    return parser


def check_health(client: httpx.Client, base_url: str) -> None:
    response = client.get(f"{base_url}/health")
    response.raise_for_status()


def start_file_session(client: httpx.Client, args: argparse.Namespace) -> dict:
    audio_path = Path(args.audio_file)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    data = {
        "sample_rate": str(args.sample_rate),
        "chunk_seconds": str(args.chunk_seconds),
        "silence_timeout_seconds": str(args.silence_timeout_seconds),
        "max_session_seconds": str(args.max_session_seconds),
        "silence_threshold": str(args.silence_threshold),
        "language": args.language,
        "temperature": str(args.temperature),
        "realtime_factor": str(args.realtime_factor),
    }
    if args.analyzer_url:
        data["analyzer_url"] = args.analyzer_url
    if args.rag_url:
        data["rag_url"] = args.rag_url
    if args.tts_url:
        data["tts_url"] = args.tts_url
    if args.tts_model:
        data["tts_model"] = args.tts_model
    if args.tts_voice:
        data["tts_voice"] = args.tts_voice
    if args.tts_language:
        data["tts_language"] = args.tts_language
    if args.tts_instructions:
        data["tts_instructions"] = args.tts_instructions

    with audio_path.open("rb") as audio_file:
        files = {"file": (audio_path.name, audio_file, "audio/wav")}
        response = client.post(f"{args.base_url}{args.start_endpoint}", files=files, data=data)
        response.raise_for_status()
        return response.json()


def poll_session(client: httpx.Client, base_url: str, session_id: str, poll_interval: float, max_polls: int) -> dict:
    previous_samples = None
    previous_parts = None
    previous_response = ""
    response_header_printed = False
    previous_tts_segments = 0
    last_payload = None

    for _ in range(max_polls):
        response = client.get(f"{base_url}/api/v1/sessions/{session_id}")
        response.raise_for_status()
        payload = response.json()
        last_payload = payload

        captured_audio_seconds = payload.get("captured_audio_seconds")
        transcript_parts = payload.get("transcript_parts", [])
        if captured_audio_seconds != previous_samples or len(transcript_parts) != previous_parts:
            print(
                f"status={payload['status']} captured_audio_seconds={captured_audio_seconds} "
                f"transcript_parts={len(transcript_parts)}"
            )
            previous_samples = captured_audio_seconds
            previous_parts = len(transcript_parts)

        response_text = payload.get("response", "") or ""
        if response_text.startswith(previous_response) and len(response_text) > len(previous_response):
            if not response_header_printed:
                print("\nStreaming RAG response:\n")
                response_header_printed = True
            delta = response_text[len(previous_response) :]
            print(delta, end="", flush=True)
            previous_response = response_text

        tts_segments = payload.get("tts_audio_segments", [])
        if len(tts_segments) > previous_tts_segments:
            for segment in tts_segments[previous_tts_segments:]:
                print(f"\nTTS audio ready: {segment['audio_file']}")
            previous_tts_segments = len(tts_segments)

        if payload["status"] not in {"running", "stopping"}:
            if response_header_printed:
                print()
            return payload

        time.sleep(poll_interval)

    raise TimeoutError(f"Session {session_id} did not complete after {max_polls} polls: {json.dumps(last_payload, indent=2)}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        with httpx.Client(trust_env=False, timeout=args.request_timeout) as client:
            check_health(client, args.base_url)
            started = start_file_session(client, args)
            session_id = started["session_id"]
            print(f"started session_id={session_id}")

            completed = poll_session(
                client=client,
                base_url=args.base_url,
                session_id=session_id,
                poll_interval=args.poll_interval,
                max_polls=args.max_polls,
            )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(completed, indent=2))
    transcript = completed.get("transcript", "")
    if transcript:
        print("\nFinal transcript:\n")
        print(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
