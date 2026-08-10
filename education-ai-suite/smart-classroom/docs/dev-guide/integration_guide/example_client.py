"""
Smart Classroom Session API - example client.

Submits a transcription + video-analytics task, polls its status every 10s,
and prints the output directory when it finishes.

Usage:
    python example_client.py

Edit HOST / AUDIO_PATH / VIDEO_SOURCES below to match your setup.
Uses only the Python standard library (no extra dependencies).
"""

import json
import sys
import time
import urllib.request
import urllib.error

# ---- configuration: edit these ----
HOST = "http://127.0.0.1:8000"
# AUDIO_PATH = r"C:\media\class1.wav"
# VIDEO_SOURCES = {
#     "front": r"C:\media\front.mp4",
#     "back": r"C:\media\back.mp4",
# }
AUDIO_PATH = r"C:\Users\user\jianfeng\EDU-AI\PR\edu-ai-suite-20260-mandarin-test-files\input_part_5min.wav"
VIDEO_SOURCES = {
    "front": r"C:\Users\user\jianfeng\EDU-AI\PR\edu-ai-suite-20260-mandarin-test-files\qian5.mp4",
    "back": r"C:\Users\user\jianfeng\EDU-AI\PR\edu-ai-suite-20260-mandarin-test-files\hou5.mp4",
    "content": r"C:\Users\user\jianfeng\EDU-AI\PR\edu-ai-suite-20260-mandarin-test-files\board5.mp4",
}
STAGES = ["transcribe", "va", "summarize", "mindmap"]
POLL_INTERVAL_SEC = 5
# ------------------------------------


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        HOST + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path):
    with urllib.request.urlopen(HOST + path) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _as_curl(path, payload):
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    return (
        f"curl --location '{HOST}{path}' \\\n"
        f"--header 'Content-Type: application/json' \\\n"
        f"--data '{body}'"
    )


def _check_service():
    """Verify the service is reachable before submitting. Exit early if not."""
    try:
        with urllib.request.urlopen(HOST + "/health", timeout=5) as resp:
            if resp.status == 200:
                print(f"Service OK at {HOST}")
                return
            print(f"Service returned HTTP {resp.status} at {HOST}")
    except urllib.error.URLError as e:
        print(f"Cannot reach service at {HOST}: {e.reason}")
    except Exception as e:
        print(f"Cannot reach service at {HOST}: {e}")
    print("Make sure Smart Classroom is running and HOST is correct.")
    sys.exit(1)


def main():
    # 0. Check the service is up
    _check_service()

    # 1. Submit the task
    payload = {
        "audio_path": AUDIO_PATH,
        "video_sources": VIDEO_SOURCES,
        "stages": STAGES,
    }
    print("Submitting task... equivalent curl command:\n")
    print(_as_curl("/sessions/process", payload))
    print()
    result = _post("/sessions/process", payload)
    session_id = result["session_id"]
    print(f"  session_id : {session_id}")
    print(f"  output_dir : {result['output_dir']}")

    # 2. Poll status every POLL_INTERVAL_SEC seconds
    print("\nPolling status...")
    while True:
        status = _get(f"/sessions/{session_id}/status")
        state = status["state"]
        stage = status.get("current_stage")
        print(f"  state={state}  current_stage={stage}  stages={status['stages']}")

        if state == "completed":
            print("\n=== Task completed ===")
            _print_summary(status)
            break
        if state == "failed":
            print("\n=== Task failed ===")
            print(f"  error: {status.get('error')}")
            _print_summary(status)
            break

        time.sleep(POLL_INTERVAL_SEC)


def _print_summary(status):
    sources = status.get("sources") or {}
    video = sources.get("video") or {}
    src_video = ", ".join(f"{k}={v}" for k, v in video.items()) or "-"
    src_audio = sources.get("audio") or "-"
    done_stages = ", ".join(k for k, v in (status.get("stages") or {}).items() if v == "done") or "-"

    rows = [
        ("session_id", status.get("session_id")),
        ("start_time", status.get("started_at")),
        ("end_time", status.get("updated_at")),
        ("source video", src_video),
        ("source audio", src_audio),
        ("stages(done)", done_stages),
        ("output_dir", status.get("output_dir")),
    ]
    key_w = max(len(k) for k, _ in rows)
    val_w = max(len(str(v)) for _, v in rows)
    line = "+" + "-" * (key_w + 2) + "+" + "-" * (val_w + 2) + "+"
    print(line)
    for k, v in rows:
        print(f"| {k.ljust(key_w)} | {str(v).ljust(val_w)} |")
    print(line)


if __name__ == "__main__":
    main()
