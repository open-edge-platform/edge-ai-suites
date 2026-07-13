#!/usr/bin/env python3
"""60-second-per-device benchmark for the DL Streamer polyp pipeline —
**live Basler acA1920-150uc source** variant.

Mirrors scripts/bench_60s.py 1-for-1 in methodology so the results are
directly comparable to the recorded-video MTL/PTL benches under
`_dev_notes/bench_60s_*.json`. The only difference is the source:

    file/video:  filesrc … ! decodebin ! …                (bench_60s.py)
    basler live: pypylon → fdsrc fd=0 ! rawvideoparse ! …  (this script)

Per-device loop (GPU → CPU → NPU):
  1. POST /stop  (clean state)
  2. POST /start with {"device": DEV, "source": {"kind": "basler", "arg": SERIAL}}
  3. Sample /api/status every 2 s for 60 s, printing per-tick backend
     fps + infer/proc/e2e latency and cumulative frame_id
  4. POST /stop
  5. Grep /frames/latency.log for raw `frame_latency` (e2e) and
     `element-latency` per element — independent of the backend parser
  6. Read bogus-box drop counter from pipeline stderr
  7. Read basler_reader fps + warnings from pipeline stderr

Outputs:
  * MD summary table to stdout
  * Raw JSON to `_dev_notes/slice-E-artifacts/bench_60s_basler_all_<ts>.json`
  * Raw stderr snapshot to `_dev_notes/slice-E-artifacts/pipeline_stderr_basler_<DEV>_<ts>.log`
  * Raw tracer log tail to `_dev_notes/slice-E-artifacts/latency_tracer_basler_<DEV>_<ts>.log`
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone


BASE = "http://localhost:8080/api"
DEVICES = ["GPU", "CPU", "NPU"]
RUN_SECONDS = 60
WARM_SECONDS = 8  # basler reader ramp + queue1 fill
BASLER_SERIAL = "40067928"

OUT_DIR = pathlib.Path(__file__).resolve().parents[1] / "_dev_notes" / "slice-E-artifacts"
CONTAINER = "surgical-pipeline"
LOG_PATH = "/frames/latency.log"

BASLER_FPS_RE = re.compile(r"\[basler_reader\]\s+(\d+)\s+frames\s+in\s+([\d.]+)s\s+=\s+([\d.]+)\s+fps")


# ── HTTP helpers ─────────────────────────────────────────────────────────

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


# ── Raw-log parsing (independent of backend) ─────────────────────────────

def raw_e2e_stats() -> tuple[float, float, int]:
    """`frame_latency` = pipeline latency_tracer_pipeline metric (ms).

    Note: on a live-camera source this is the true glass-to-glass residence;
    on `filesrc` it includes decoder pre-buffer. See
    `_dev_notes/dls-latency-metric-justification.md` §4b.
    """
    proc = subprocess.run(
        ["docker", "exec", CONTAINER, "bash", "-lc",
         f"grep -oE 'frame_latency=\\(double\\)[0-9.]+' {LOG_PATH} | "
         "awk -F'[()]' '{print $3}'"],
        capture_output=True, text=True, timeout=15,
    )
    vals = [float(v) for v in proc.stdout.strip().split("\n") if v.strip()]
    if not vals:
        return 0.0, 0.0, 0
    vals.sort()
    p99 = vals[max(0, int(round(len(vals) * 0.99)) - 1)]
    return statistics.fmean(vals), p99, len(vals)


def raw_element_stats(elem_name: str) -> tuple[float, float, int]:
    """Per-element latency (ms) from tracer log — same query as bench_60s.py."""
    proc = subprocess.run(
        ["docker", "exec", CONTAINER, "bash", "-lc",
         f"grep -oE 'element-latency,[^;]*element=\\(string\\){elem_name},[^;]*time=\\(guint64\\)[0-9]+' "
         f"{LOG_PATH} | grep -oE 'time=\\(guint64\\)[0-9]+' | awk -F')' '{{print $2}}'"],
        capture_output=True, text=True, timeout=15,
    )
    vals = [int(v) / 1_000_000.0 for v in proc.stdout.strip().split("\n") if v.strip()]
    if not vals:
        return 0.0, 0.0, 0
    vals.sort()
    p99 = vals[max(0, int(round(len(vals) * 0.99)) - 1)]
    return statistics.fmean(vals), p99, len(vals)


def raw_infer_stats() -> tuple[float, float, int]:
    """Alias of raw_element_stats('det') to match bench_60s.py column labels."""
    return raw_element_stats("det")


def bbox_dropped() -> int:
    """Read the last 'BBoxFilter: dropped N' counter emitted to stderr."""
    proc = subprocess.run(
        ["docker", "logs", CONTAINER],
        capture_output=True, text=True, timeout=15,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    last = 0
    for line in log.splitlines():
        if "BBoxFilter: dropped" in line:
            try:
                last = int(line.split("dropped", 1)[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
    return last


def basler_reader_stats() -> dict:
    """Parse basler_reader's own stderr lines: rolling fps + warnings."""
    proc = subprocess.run(
        ["docker", "logs", CONTAINER],
        capture_output=True, text=True, timeout=15,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    fps_samples: list[float] = []
    warnings: list[str] = []
    for line in log.splitlines():
        m = BASLER_FPS_RE.search(line)
        if m:
            fps_samples.append(float(m.group(3)))
            continue
        if "[basler_reader]" in line and ("warn" in line.lower() or "error" in line.lower()):
            warnings.append(line.strip())
    return {
        "sensor_fps_samples": fps_samples,
        "sensor_fps_last":    fps_samples[-1] if fps_samples else 0.0,
        "sensor_fps_median":  round(statistics.median(fps_samples), 2) if fps_samples else 0.0,
        "warnings":           warnings[-5:],  # last 5 only
    }


def snapshot_logs(device: str, ts: str) -> tuple[pathlib.Path, pathlib.Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stderr_path  = OUT_DIR / f"pipeline_stderr_basler_{device}_{ts}.log"
    tracer_path  = OUT_DIR / f"latency_tracer_basler_{device}_{ts}.log"
    subprocess.run(
        ["bash", "-lc",
         f"docker logs {CONTAINER} 2>&1 | tail -400 > {stderr_path}"],
        check=False, timeout=15,
    )
    subprocess.run(
        ["bash", "-lc",
         f"docker exec {CONTAINER} bash -lc 'tail -8000 {LOG_PATH} | grep latency_tracer_element | tail -3000' > {tracer_path}"],
        check=False, timeout=15,
    )
    return stderr_path, tracer_path


# ── per-device runner ───────────────────────────────────────────────────

def run_one(device: str, ts: str) -> dict:
    print(f"\n=== {device} (basler live) ===", flush=True)

    # 1. Clean state
    try:
        post("/stop")
        time.sleep(2)
    except Exception as exc:
        print(f"  /stop (ignored): {exc}", flush=True)

    # 2. Start with basler source + this device
    start_body = {
        "device": device,
        "source": {"kind": "basler", "arg": BASLER_SERIAL},
    }
    print(f"  /start body: {start_body}", flush=True)
    start_resp = post("/start", start_body)
    print(f"  /start resp: {start_resp}", flush=True)

    # 3. Warm-up
    print(f"  warm-up {WARM_SECONDS}s (reader ramp + queue1 fill)", flush=True)
    time.sleep(WARM_SECONDS)

    # 4. Sample /api/status every 2 s for RUN_SECONDS
    print(f"  sampling {RUN_SECONDS}s", flush=True)
    t0 = time.time()
    last_status: dict = {}
    fps_series: list[float] = []
    e2e_mean_series: list[float] = []
    e2e_p99_series: list[float] = []
    while time.time() - t0 < RUN_SECONDS:
        try:
            last_status = get_status()
        except Exception as exc:
            print(f"    status error: {exc}", flush=True)
            time.sleep(2)
            continue
        elapsed = int(time.time() - t0)
        inf = (last_status.get("inference") or {})
        fps  = inf.get("delivered_fps", 0.0) or 0.0
        e2em = inf.get("e2e_mean_ms", 0.0) or 0.0
        e2ep = inf.get("e2e_p99_ms", 0.0) or 0.0
        if fps > 0:
            fps_series.append(fps)
        if e2em > 0:
            e2e_mean_series.append(e2em)
        if e2ep > 0:
            e2e_p99_series.append(e2ep)
        print(
            f"    t={elapsed:2d}s fps={fps:5.2f} "
            f"infer={inf.get('infer_mean_ms', 0):5.1f}/{inf.get('infer_p99_ms', 0):5.1f}ms "
            f"proc={inf.get('processing_mean_ms', 0):5.1f}/{inf.get('processing_p99_ms', 0):5.1f}ms "
            f"e2e={e2em:6.1f}/{e2ep:6.1f}ms "
            f"frames={inf.get('frame_id', 0)}",
            flush=True,
        )
        time.sleep(2)

    # 5. Grab final snapshot BEFORE stop so counters are fresh
    try:
        final = get_status()
    except Exception:
        final = last_status
    inf = final.get("inference") or {}

    # 6. Independent raw-log verification (still inside the container)
    raw_e2e_mean,  raw_e2e_p99,  raw_e2e_n  = raw_e2e_stats()
    raw_inf_mean,  raw_inf_p99,  raw_inf_n  = raw_infer_stats()
    per_elem: dict[str, dict] = {}
    for elem in ("det", "gvatrack0", "gvametaconvert0", "drawer", "vajpegenc0",
                 "videoconvert1", "videoconvert2", "queue1"):
        m, p, n = raw_element_stats(elem)
        per_elem[elem] = {"mean_ms": round(m, 2), "p99_ms": round(p, 2), "n": n}

    dropped     = bbox_dropped()
    reader_stat = basler_reader_stats()

    # 7. Snapshot the logs for this device
    stderr_p, tracer_p = snapshot_logs(device, ts)

    # 8. Stop
    try:
        post("/stop")
    except Exception:
        pass
    time.sleep(3)

    return {
        "device": device,

        # Backend-computed metrics (same shape as bench_60s.py)
        "fps": inf.get("delivered_fps", 0.0),
        "fps_series_median":  round(statistics.median(fps_series), 2) if fps_series else 0.0,
        "fps_series_mean":    round(statistics.fmean(fps_series), 2) if fps_series else 0.0,
        "fps_series_min":     round(min(fps_series), 2) if fps_series else 0.0,
        "backend_infer_mean": inf.get("infer_mean_ms", 0.0),
        "backend_infer_p99":  inf.get("infer_p99_ms", 0.0),
        "backend_proc_mean":  inf.get("processing_mean_ms", 0.0),
        "backend_proc_p99":   inf.get("processing_p99_ms", 0.0),
        "backend_e2e_mean":   inf.get("e2e_mean_ms", 0.0),
        "backend_e2e_p99":    inf.get("e2e_p99_ms", 0.0),

        # Raw-log verification
        "raw_infer_mean": round(raw_inf_mean, 2),
        "raw_infer_p99":  round(raw_inf_p99, 2),
        "raw_infer_n":    raw_inf_n,
        "raw_e2e_mean":   round(raw_e2e_mean, 2),
        "raw_e2e_p99":    round(raw_e2e_p99, 2),
        "raw_e2e_n":      raw_e2e_n,

        # Per-element breakdown
        "per_element": per_elem,

        # Detection semantics (Basler pointed at lab, so expect ~0)
        "detection_rate":     inf.get("detection_rate", 0.0),
        "distinct_polyps":    inf.get("distinct_polyps", 0),
        "frames_processed":   inf.get("frame_id", 0),
        "frames_with_polyp":  inf.get("frames_with_detection", 0),
        "cumulative_dets":    inf.get("cumulative_detections", 0),
        "peak_conf":          inf.get("peak_confidence", 0.0),
        "bogus_boxes_dropped": dropped,

        # Basler-reader specifics (source-side sanity)
        "basler_reader": reader_stat,

        # Artifact pointers
        "artifacts": {
            "pipeline_stderr": str(stderr_p.relative_to(OUT_DIR.parent.parent)),
            "latency_tracer":  str(tracer_p.relative_to(OUT_DIR.parent.parent)),
        },
    }


# ── main ────────────────────────────────────────────────────────────────

def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"[bench_60s_basler] timestamp = {ts}", flush=True)
    print(f"[bench_60s_basler] serial    = {BASLER_SERIAL}", flush=True)
    print(f"[bench_60s_basler] devices   = {DEVICES}", flush=True)
    print(f"[bench_60s_basler] duration  = {RUN_SECONDS}s per device "
          f"(+{WARM_SECONDS}s warm-up)", flush=True)

    results = []
    for dev in DEVICES:
        try:
            results.append(run_one(dev, ts))
        except Exception as exc:
            print(f"  {dev} FAILED: {exc}", flush=True)
            results.append({"device": dev, "error": str(exc)})

    # ── summary table (same layout as bench_60s.py) ─────────────────────
    print("\n\n=================== 60-s BASLER-LIVE BENCHMARK SUMMARY ===================\n")
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
    print("| Device | Infer mean · p99 (raw ms, N) | E2E mean · p99 (raw ms, N) |")
    print("|--------|-------------------------------|-----------------------------|")
    for r in results:
        if "error" in r:
            continue
        print(
            f"| {r['device']} | "
            f"{r['raw_infer_mean']:.1f} · {r['raw_infer_p99']:.1f}  (N={r['raw_infer_n']}) | "
            f"{r['raw_e2e_mean']:.1f} · {r['raw_e2e_p99']:.1f}  (N={r['raw_e2e_n']}) |"
        )

    print("\n### Per-element latency breakdown (raw ms, from tracer log)\n")
    print("| Device | det | gvatrack0 | gvametaconvert0 | drawer | vajpegenc0 | queue1 | sum(det..jpeg) |")
    print("|--------|-----|-----------|-----------------|--------|------------|--------|----------------|")
    for r in results:
        if "error" in r:
            continue
        pe = r["per_element"]
        core = ("det", "gvatrack0", "gvametaconvert0", "drawer", "vajpegenc0")
        cells = " | ".join(f"{pe[e]['mean_ms']:.2f}\u00b7{pe[e]['p99_ms']:.2f}" for e in core)
        s = sum(pe[e]["mean_ms"] for e in core)
        print(f"| **{r['device']}** | {cells} | {pe['queue1']['mean_ms']:.2f}\u00b7{pe['queue1']['p99_ms']:.2f} | {s:.2f} |")

    print("\n### Basler reader sensor-side FPS (source of truth for camera cadence)\n")
    print("| Device | reader_fps median | reader_fps last | warnings (tail) |")
    print("|--------|-------------------|-----------------|-----------------|")
    for r in results:
        if "error" in r:
            continue
        br = r["basler_reader"]
        warns = "; ".join(br["warnings"])[:80] if br["warnings"] else "(none)"
        print(f"| **{r['device']}** | {br['sensor_fps_median']:.2f} | {br['sensor_fps_last']:.2f} | {warns} |")

    # ── persist ─────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"bench_60s_basler_all_{ts}.json"
    out.write_text(json.dumps({
        "run_seconds":    RUN_SECONDS,
        "warm_seconds":   WARM_SECONDS,
        "timestamp_utc":  ts,
        "source_kind":    "basler",
        "source_arg":     BASLER_SERIAL,
        "results":        results,
    }, indent=2))
    print(f"\n[saved raw JSON \u2192 {out}]")


if __name__ == "__main__":
    main()
