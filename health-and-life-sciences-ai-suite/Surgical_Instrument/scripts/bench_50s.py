#!/usr/bin/env python3
"""50-second-per-device benchmark for the DL Streamer polyp pipeline.

For each device (GPU, CPU, NPU):
  1. Reset the backend session
  2. Set device
  3. Start
  4. Sample /api/status every 1s for exactly 50s
  5. Stop
  6. Independently verify by grepping frame_latency from
     /frames/latency.log via `docker exec` (no trust in backend parser)
  7. Query BBoxFilter drop counter from pipeline stderr

Prints a Markdown summary table when done.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
import urllib.request


BASE = "http://localhost:8080/api"
DEVICES = ["GPU", "CPU", "NPU"]
RUN_SECONDS = 50


def post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode() or "{}")


def get_status() -> dict:
    with urllib.request.urlopen(f"{BASE}/status", timeout=5) as r:
        return json.loads(r.read().decode())


def raw_e2e_stats() -> tuple[float, float, int]:
    """Grep frame_latency straight from the pipeline's log file."""
    proc = subprocess.run(
        ["docker", "exec", "surgical-pipeline", "bash", "-lc",
         "grep -oE 'frame_latency=\\(double\\)[0-9.]+' /frames/latency.log | "
         "awk -F'[()]' '{print $3}'"],
        capture_output=True, text=True, timeout=15,
    )
    vals = [float(v) for v in proc.stdout.strip().split("\n") if v.strip()]
    if not vals:
        return 0.0, 0.0, 0
    vals.sort()
    p99 = vals[max(0, int(round(len(vals) * 0.99)) - 1)]
    return statistics.fmean(vals), p99, len(vals)


def raw_infer_stats() -> tuple[float, float, int]:
    """Grep gvadetect element-latency straight from the pipeline's log file."""
    proc = subprocess.run(
        ["docker", "exec", "surgical-pipeline", "bash", "-lc",
         "grep -oE 'element-latency,[^;]*element=\\(string\\)det[0-9]*,[^;]*time=\\(guint64\\)[0-9]+' "
         "/frames/latency.log | grep -oE 'time=\\(guint64\\)[0-9]+' | awk -F')' '{print $2}'"],
        capture_output=True, text=True, timeout=15,
    )
    vals = [int(v) / 1_000_000.0 for v in proc.stdout.strip().split("\n") if v.strip()]
    if not vals:
        return 0.0, 0.0, 0
    vals.sort()
    p99 = vals[max(0, int(round(len(vals) * 0.99)) - 1)]
    return statistics.fmean(vals), p99, len(vals)


def bbox_dropped() -> int:
    proc = subprocess.run(
        ["docker", "logs", "surgical-pipeline"],
        capture_output=True, text=True, timeout=15,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    last = 0
    for line in log.splitlines():
        if "BBoxFilter: dropped" in line:
            # ' ... dropped 12 oversize ROIs ...'
            try:
                last = int(line.split("dropped", 1)[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
    return last


def run_one(device: str) -> dict:
    print(f"\n=== {device} ===", flush=True)
    # Always try /stop first so a leftover run from a previous iteration
    # doesn't 409 the /reset.
    try:
        post("/stop")
        time.sleep(2)
    except Exception:
        pass
    post("/reset")
    post("/device", {"device": device})
    post("/start")

    # wait 3s for pipeline to reach steady state, then sample 50s
    time.sleep(3)
    print(f"  sampling {RUN_SECONDS}s", flush=True)
    t0 = time.time()
    last_status: dict = {}
    while time.time() - t0 < RUN_SECONDS:
        try:
            last_status = get_status()
        except Exception as exc:  # noqa: BLE001
            print(f"    status error: {exc}", flush=True)
        elapsed = int(time.time() - t0)
        inf = (last_status.get("inference") or {})
        print(
            f"    t={elapsed:2d}s fps={inf.get('delivered_fps', 0):5.2f} "
            f"infer={inf.get('infer_mean_ms', 0):5.1f}/{inf.get('infer_p99_ms', 0):5.1f}ms "
            f"proc={inf.get('processing_mean_ms', 0):5.1f}/{inf.get('processing_p99_ms', 0):5.1f}ms "
            f"e2e={inf.get('e2e_mean_ms', 0):6.1f}/{inf.get('e2e_p99_ms', 0):6.1f}ms "
            f"frames={inf.get('frame_id', 0)}",
            flush=True,
        )
        time.sleep(2)

    try:
        final = get_status()
    except Exception:
        final = {}
    inf = final.get("inference") or {}
    try:
        raw_e2e_mean, raw_e2e_p99, raw_e2e_n = raw_e2e_stats()
    except Exception as exc:  # noqa: BLE001
        print(f"    raw e2e parse failed: {exc}", flush=True)
        raw_e2e_mean, raw_e2e_p99, raw_e2e_n = 0.0, 0.0, 0
    try:
        raw_inf_mean, raw_inf_p99, raw_inf_n = raw_infer_stats()
    except Exception as exc:  # noqa: BLE001
        print(f"    raw infer parse failed: {exc}", flush=True)
        raw_inf_mean, raw_inf_p99, raw_inf_n = 0.0, 0.0, 0
    dropped = bbox_dropped()

    try:
        post("/stop")
    except Exception:
        pass
    time.sleep(3)

    return {
        "device": device,
        "fps": inf.get("delivered_fps", 0.0),
        "backend_infer_mean": inf.get("infer_mean_ms", 0.0),
        "backend_infer_p99":  inf.get("infer_p99_ms", 0.0),
        "backend_proc_mean":  inf.get("processing_mean_ms", 0.0),
        "backend_proc_p99":   inf.get("processing_p99_ms", 0.0),
        "backend_e2e_mean":   inf.get("e2e_mean_ms", 0.0),
        "backend_e2e_p99":    inf.get("e2e_p99_ms", 0.0),
        "raw_infer_mean": raw_inf_mean,
        "raw_infer_p99":  raw_inf_p99,
        "raw_infer_n":    raw_inf_n,
        "raw_e2e_mean":   raw_e2e_mean,
        "raw_e2e_p99":    raw_e2e_p99,
        "raw_e2e_n":      raw_e2e_n,
        "detection_rate": inf.get("detection_rate", 0.0),
        "distinct_polyps": inf.get("distinct_polyps", 0),
        "frames_processed": inf.get("frame_id", 0),
        "frames_with_polyp": inf.get("frames_with_detection", 0),
        "cumulative_dets": inf.get("cumulative_detections", 0),
        "peak_conf": inf.get("peak_confidence", 0.0),
        "bogus_boxes_dropped": dropped,
    }


def main() -> None:
    results = []
    for dev in DEVICES:
        try:
            results.append(run_one(dev))
        except Exception as exc:  # noqa: BLE001
            print(f"  {dev} FAILED: {exc}", flush=True)
            results.append({"device": dev, "error": str(exc)})

    # ---- summary ----
    print("\n\n=================== 50-s BENCHMARK SUMMARY ===================\n")
    hdr = (
        "| Device | FPS | Infer mean · p99 (ms) | Processing mean · p99 (ms) | "
        "End-to-end mean · p99 (ms) | Detection rate | Distinct polyps | "
        "Frames (proc/pos) | Peak conf | Bogus dropped |"
    )
    sep = (
        "|--------|-----|-----------------------|-----------------------------|"
        "-----------------------------|----------------|------------------|"
        "---------------------|-----------|---------------|"
    )
    print(hdr)
    print(sep)
    for r in results:
        if "error" in r:
            print(f"| {r['device']} | ERROR | {r['error']} | | | | | | | |")
            continue
        print(
            f"| **{r['device']}** | {r['fps']:.1f} | "
            f"{r['backend_infer_mean']:.1f} · {r['backend_infer_p99']:.1f} | "
            f"{r['backend_proc_mean']:.1f} · {r['backend_proc_p99']:.1f} | "
            f"{r['backend_e2e_mean']:.1f} · {r['backend_e2e_p99']:.1f} | "
            f"{r['detection_rate']*100:.1f}% | "
            f"{r['distinct_polyps']} | "
            f"{r['frames_processed']}/{r['frames_with_polyp']} | "
            f"{r['peak_conf']:.2f} | "
            f"{r['bogus_boxes_dropped']} |"
        )

    print("\n### Raw-log verification (independent of backend parser)\n")
    print("| Device | Infer mean · p99 (raw ms, N samples) | E2E mean · p99 (raw ms, N samples) |")
    print("|--------|---------------------------------------|-------------------------------------|")
    for r in results:
        if "error" in r:
            continue
        print(
            f"| **{r['device']}** | "
            f"{r['raw_infer_mean']:.1f} · {r['raw_infer_p99']:.1f}  (N={r['raw_infer_n']}) | "
            f"{r['raw_e2e_mean']:.1f} · {r['raw_e2e_p99']:.1f}  (N={r['raw_e2e_n']}) |"
        )

    print("\nSources: Infer      = GStreamer core `latency` tracer → element-latency for element=det")
    print("         Processing = per-frame sum of element-latency across gvadetect + gvatrack + gvametaconvert + gvawatermark + jpegenc")
    print("         E2E        = Intel DL Streamer `latency_tracer` → frame_latency on latency_tracer_pipeline (source → sink residence, includes decode)")


if __name__ == "__main__":
    main()
