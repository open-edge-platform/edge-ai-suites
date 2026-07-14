#!/usr/bin/env python3
"""50-second per-device benchmark. Aggregates:
   - delivered FPS + detection stats from backend /api/status
   - gvadetect frame_latency (avg + p99) from raw latency_tracer_element log
   - critical-path end-to-end = sum of avg element_latency across the main path
     (excludes videorate/identity pacing artifacts)
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request

BASE = "http://localhost:8080/api"
LOG_PATH = "/frames/latency.log"
CONTAINER = "surgical-pipeline"

# Elements on the buffer's critical path (source→sink through the JPEG branch).
# Excludes videorate/identity — those are pacing, not processing.
CRIT_PATH = {
    "decodebin",
    "videoconvert0",
    "videoscale0",
    "capsfilter0",
    "det",
    "gvatrack0",
    "gvametaconvert0",
    "tee0",
    "queue1",
    "gvawatermark0",
    "videoconvert1",
    "vajpegenc0",
    "multifilesink0",
}

DEV_LATENCY_RE = re.compile(
    r"latency_tracer_element,\s*name=\(string\)(?P<n>[\w\-]+),\s*"
    r"frame_latency=\(double\)[\d.]+,\s*"
    r"avg=\(double\)(?P<avg>[\d.]+),\s*"
    r"min=\(double\)(?P<min>[\d.]+),\s*"
    r"max=\(double\)(?P<max>[\d.]+),"
)


def http(path: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        method=method,
        data=data,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def parse_element_avg(log_tail: str) -> dict[str, float]:
    """Return last-seen `avg` per element name."""
    out: dict[str, float] = {}
    for line in log_tail.splitlines():
        m = DEV_LATENCY_RE.search(line)
        if m:
            out[m.group("n")] = float(m.group("avg"))
    return out


def bench(device: str, seconds: int = 50) -> dict:
    print(f"\n===== {device} =====")
    # Ensure clean state
    try:
        http("/stop", "POST")
    except Exception:
        pass
    time.sleep(2)
    try:
        http("/reset", "POST")
    except Exception:
        pass
    http("/device", "POST", {"device": device})
    start_resp = http("/start", "POST")
    print("start:", start_resp)

    # Warm-up: skip first 5s so element traces stabilize
    time.sleep(5)
    print("warm-up done, sampling...")

    samples = []
    end = time.time() + seconds
    while time.time() < end:
        try:
            st = http("/status")
            if st.get("inference"):
                samples.append(st["inference"])
        except Exception as exc:
            print("status err:", exc)
        time.sleep(2)

    final = samples[-1] if samples else {}

    # Grab element-latency tail from the container
    tail = subprocess.check_output(
        ["docker", "exec", CONTAINER, "bash", "-lc",
         f"tail -6000 {LOG_PATH} | grep latency_tracer_element"],
        text=True, timeout=10,
    )
    elem_avg = parse_element_avg(tail)

    # Critical path total: sum avgs for elements on the source→JPEG-sink path
    crit_total = sum(v for k, v in elem_avg.items() if k in CRIT_PATH)
    det_avg = elem_avg.get("det", 0.0)

    # Detection element p99 from raw values in tail
    det_vals: list[float] = []
    for line in tail.splitlines():
        m = DEV_LATENCY_RE.search(line)
        if m and m.group("n") == "det":
            # parse frame_latency (not avg) for percentile
            fl = re.search(r"frame_latency=\(double\)([\d.]+)", line)
            if fl:
                det_vals.append(float(fl.group(1)))
    det_vals.sort()
    det_p99 = det_vals[int(0.99 * len(det_vals))] if det_vals else 0.0

    result = {
        "device": device,
        "delivered_fps": final.get("delivered_fps", 0),
        "distinct_polyps": final.get("distinct_polyps", 0),
        "frames_processed": final.get("frame_id", 0),
        "frames_with_detection": final.get("frames_with_detection", 0),
        "detection_rate": final.get("detection_rate", 0) * 100,
        "peak_conf": final.get("peak_confidence", 0),
        "cumulative_detections": final.get("cumulative_detections", 0),
        "uptime_s": final.get("uptime_s", 0),
        "gvadetect_mean_ms": det_avg,
        "gvadetect_p99_ms": det_p99,
        "critical_path_ms": crit_total,
        "elements": {k: round(v, 2) for k, v in sorted(elem_avg.items(), key=lambda kv: -kv[1])[:8]},
    }

    print("stop:", http("/stop", "POST"))
    time.sleep(3)
    http("/reset", "POST")
    return result


if __name__ == "__main__":
    results = []
    for dev in ("GPU", "CPU", "NPU"):
        try:
            results.append(bench(dev))
        except Exception as exc:
            print(f"{dev} failed: {exc}")
            results.append({"device": dev, "error": str(exc)})

    print("\n\n========== SUMMARY ==========")
    print(json.dumps(results, indent=2, default=str))
