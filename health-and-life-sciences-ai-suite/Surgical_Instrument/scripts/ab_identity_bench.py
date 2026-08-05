#!/usr/bin/env python3
"""A/B benchmark: pipeline WITH vs WITHOUT the `identity` element.

Runs a gst-launch subprocess with the GStreamer core `latency` tracer
enabled (same instrumentation the production launcher uses), collects
samples for N seconds, then prints a JSON summary of FPS + latency
percentiles. Designed to run inside the `surgical-pipeline` container.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import threading
import time
from typing import List

LATENCY_RE = re.compile(r"(?<!element-)latency,.*time=\(guint64\)(\d+)")
FPS_TOTAL_RE = re.compile(r"FpsCounter\(average ([\d.]+)sec\):\s*total=([\d.]+)")


def build_cmd(with_identity: bool) -> List[str]:
    parts = [
        "gst-launch-1.0", "-e",
        "gencamsrc", "serial=40067928", "pixel-format=bayerbggr", "frame-rate=60",
        "!", "bayer2rgb", "!", "videoscale", "!", "videoconvert",
        "!", "video/x-raw,width=1280,height=720,format=NV12",
    ]
    if with_identity:
        parts += ["!", "identity"]
    parts += [
        "!", "queue", "max-size-buffers=1", "max-size-bytes=0",
        "max-size-time=16000000", "leaky=downstream",
        "!", "gvadetect",
        "model=/models/yolo11n_polyp/best_openvino_model/best.xml",
        "device=GPU", "threshold=0.5", "pre-process-backend=ie", "nireq=1",
        "ie-config=PERFORMANCE_HINT=LATENCY",
        "scheduling-policy=latency", "batch-size=1",
        "!", "queue", "max-size-buffers=1", "max-size-bytes=0",
        "max-size-time=16000000", "leaky=downstream",
        "!", "gvawatermark", "!", "gvafpscounter", "interval=1",
        "!", "fakesink", "sync=false",
    ]
    return ["taskset", "-c", "3-4", "chrt", "-f", "70"] + parts


def percentile(values: List[float], p: int) -> float:
    if not values:
        return 0.0
    idx = max(0, min(len(values) - 1, int((p / 100.0) * len(values) + 0.5) - 1))
    return values[idx]


def run(label: str, with_identity: bool, duration_s: float) -> dict:
    env = os.environ.copy()
    env["GST_TRACERS"] = "latency(flags=pipeline)"
    env["GST_DEBUG"] = "GST_TRACER:7"

    cmd = build_cmd(with_identity)
    print(f"\n=== [{label}] identity={'YES' if with_identity else 'NO '} ===", flush=True)
    print(" ".join(cmd), flush=True)

    proc = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    latencies_ms: List[float] = []
    fps_samples: List[float] = []
    stop = threading.Event()

    # After a short warmup, only keep samples from the steady-state window.
    warmup_s = 5.0
    started = time.monotonic()

    def pump_stderr():
        for line in proc.stderr:
            m = LATENCY_RE.search(line)
            if m and (time.monotonic() - started) >= warmup_s:
                latencies_ms.append(int(m.group(1)) / 1e6)

    def pump_stdout():
        for line in proc.stdout:
            m = FPS_TOTAL_RE.search(line)
            if m and (time.monotonic() - started) >= warmup_s:
                fps_samples.append(float(m.group(2)))

    t_err = threading.Thread(target=pump_stderr, daemon=True)
    t_out = threading.Thread(target=pump_stdout, daemon=True)
    t_err.start()
    t_out.start()

    try:
        time.sleep(duration_s)
    finally:
        # Send SIGINT so gst-launch -e propagates EOS and shuts down cleanly.
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        stop.set()
        t_err.join(timeout=2)
        t_out.join(timeout=2)

    latencies_ms.sort()
    result = {
        "label": label,
        "with_identity": with_identity,
        "duration_s": duration_s,
        "warmup_s": warmup_s,
        "latency_samples": len(latencies_ms),
        "fps_samples": len(fps_samples),
    }
    if latencies_ms:
        result.update({
            "latency_mean_ms": round(statistics.mean(latencies_ms), 3),
            "latency_p50_ms": round(percentile(latencies_ms, 50), 3),
            "latency_p90_ms": round(percentile(latencies_ms, 90), 3),
            "latency_p95_ms": round(percentile(latencies_ms, 95), 3),
            "latency_p99_ms": round(percentile(latencies_ms, 99), 3),
            "latency_max_ms": round(latencies_ms[-1], 3),
        })
    if fps_samples:
        result.update({
            "fps_mean": round(statistics.mean(fps_samples), 3),
            "fps_min": round(min(fps_samples), 3),
            "fps_max": round(max(fps_samples), 3),
        })
    print(json.dumps(result, indent=2), flush=True)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=30.0,
                    help="Seconds per run (default 30, includes 5s warmup).")
    ap.add_argument("--out", default="/tmp/ab_identity_result.json")
    args = ap.parse_args()

    results = []
    for label, ident in [("A_with_identity", True), ("B_no_identity", False)]:
        results.append(run(label, ident, args.duration))
        # Allow the camera + iGPU to settle between runs.
        time.sleep(3)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
