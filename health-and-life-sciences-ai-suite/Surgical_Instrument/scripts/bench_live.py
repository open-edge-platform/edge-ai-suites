#!/usr/bin/env python3
"""Live-camera KPI harness.

Runs the surgical pipeline for --seconds against an arbitrary source (file,
v4l2, basler) on a chosen device (CPU/GPU/NPU), samples `/api/status`
every second, tails the DL Streamer latency_tracer log, and prints
side-by-side KPIs.

Why this is separate from `bench_all_devices.py`:
- We need to run against a live-camera *source*, not iterate devices.
- Live sources don't loop on EOS — we control run-time via --seconds.
- Model accuracy is meaningless against a Basler pointed at office
  furniture; we deliberately do NOT report detection metrics unless the
  user opts in with --report-accuracy.

Usage
-----
Baseline (file, GPU):
    python3 scripts/bench_live.py --source file --arg /videos/polyp_test.mp4 \\
                                  --device GPU --seconds 60

Basler live camera (after replug on USB 3.0):
    python3 scripts/bench_live.py --source basler --arg 40067928 \\
                                  --device GPU --seconds 60

Compare two runs into one table:
    python3 scripts/bench_live.py --source file   --arg /videos/polyp_test.mp4 --device GPU --seconds 30 --out out/file.json
    python3 scripts/bench_live.py --source basler --arg 40067928              --device GPU --seconds 30 --out out/basler.json
    python3 scripts/bench_live.py --compare out/file.json out/basler.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = "http://localhost:8080/api"
PIPELINE_LOG = "/frames/latency.log"
CONTAINER = "surgical-pipeline"

# Regex mirrored from bench_all_devices.py — parses DL Streamer's
# `latency_tracer_element` GST_TRACER lines to extract per-element avg/min/max.
DEV_LATENCY_RE = re.compile(
    r"latency_tracer_element,\s*name=\(string\)(?P<n>[\w\-]+),\s*"
    r"frame_latency=\(double\)(?P<frame>[\d.]+),\s*"
    r"avg=\(double\)(?P<avg>[\d.]+),\s*"
    r"min=\(double\)(?P<min>[\d.]+),\s*"
    r"max=\(double\)(?P<max>[\d.]+),"
)


# ── HTTP helpers ─────────────────────────────────────────────────────────

def http(path: str, method: str = "GET", body: dict | None = None,
         timeout: int = 15) -> dict:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BACKEND}{path}",
        method=method,
        data=data,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else {}


# ── latency-log parsing ─────────────────────────────────────────────────

def collect_element_stats() -> dict[str, dict[str, float]]:
    """Return per-element {n_frames, avg_ms, p99_ms} from the latency log."""
    try:
        tail = subprocess.check_output(
            ["docker", "exec", CONTAINER, "bash", "-lc",
             f"tail -8000 {PIPELINE_LOG} | grep latency_tracer_element || true"],
            text=True, timeout=10,
        )
    except Exception as e:
        print(f"[bench_live] warn: couldn't tail latency log: {e}", file=sys.stderr)
        return {}

    per_elem: dict[str, list[float]] = {}
    last_avg: dict[str, float] = {}
    for line in tail.splitlines():
        m = DEV_LATENCY_RE.search(line)
        if not m:
            continue
        name = m.group("n")
        per_elem.setdefault(name, []).append(float(m.group("frame")))
        last_avg[name] = float(m.group("avg"))

    out: dict[str, dict[str, float]] = {}
    for name, vals in per_elem.items():
        vals.sort()
        p99 = vals[int(0.99 * len(vals))] if vals else 0.0
        out[name] = {
            "n_frames":  len(vals),
            "avg_ms":    round(last_avg.get(name, statistics.mean(vals)), 3),
            "p99_ms":    round(p99, 3),
        }
    return out


# ── benchmark run ───────────────────────────────────────────────────────

def run(source_kind: str, source_arg: str, device: str, seconds: int,
        warm_s: int = 5) -> dict:
    print(f"[bench_live] source={source_kind}:{source_arg!r} device={device} "
          f"duration={seconds}s (warm-up {warm_s}s)")

    # Clean state.
    try:
        http("/stop", "POST")
    except urllib.error.HTTPError:
        pass
    time.sleep(1.5)

    start_body = {
        "device": device,
        "source": {"kind": source_kind, "arg": source_arg},
    }
    resp = http("/start", "POST", start_body)
    print(f"[bench_live] /start → {resp}")

    # Give the pipeline a moment to actually reach a running state.
    time.sleep(warm_s)

    # If start failed silently at the pipeline (e.g. wrong element), fps stays 0.
    samples: list[dict] = []
    deadline = time.time() + seconds
    tick = 1.0
    next_tick = time.time() + tick
    while time.time() < deadline:
        now = time.time()
        if now < next_tick:
            time.sleep(min(0.05, next_tick - now))
            continue
        next_tick = now + tick
        try:
            st = http("/status")
            inf = st.get("inference") or {}
            samples.append({
                "t":                 round(now, 2),
                "fps":               inf.get("delivered_fps", 0.0),
                "frame_id":          inf.get("frame_id", 0),
                "e2e_mean_ms":       inf.get("e2e_mean_ms", 0.0),
                "e2e_p99_ms":        inf.get("e2e_p99_ms", 0.0),
                "cum_det":           inf.get("cumulative_detections", 0),
                "detection_rate":    inf.get("detection_rate", 0.0),
            })
        except Exception as e:
            print(f"[bench_live] status err: {e}", file=sys.stderr)

    # Stop before we parse the log so no more ticks land in it.
    try:
        http("/stop", "POST")
    except urllib.error.HTTPError:
        pass
    time.sleep(1.5)

    elems = collect_element_stats()

    # Aggregate the /status samples we captured while running.
    fps_series = [s["fps"] for s in samples if s["fps"] > 0]
    e2e_mean_series = [s["e2e_mean_ms"] for s in samples if s["e2e_mean_ms"] > 0]
    e2e_p99_series  = [s["e2e_p99_ms"]  for s in samples if s["e2e_p99_ms"]  > 0]
    frame_delta = (samples[-1]["frame_id"] - samples[0]["frame_id"]
                   if len(samples) >= 2 else 0)

    return {
        "source_kind":       source_kind,
        "source_arg":        source_arg,
        "device":            device,
        "seconds":           seconds,
        "samples":           len(samples),
        # Steady-state throughput.
        "fps_median":        round(statistics.median(fps_series), 2) if fps_series else 0,
        "fps_mean":          round(statistics.mean(fps_series), 2) if fps_series else 0,
        "fps_min":           round(min(fps_series), 2) if fps_series else 0,
        "frames_produced":   frame_delta,
        # End-to-end latency (backend view: gvametaconvert → sink).
        "e2e_mean_ms":       round(statistics.mean(e2e_mean_series), 2) if e2e_mean_series else 0,
        "e2e_p99_ms":        round(statistics.mean(e2e_p99_series), 2) if e2e_p99_series else 0,
        # gvadetect element only (inference-time proxy).
        "gvadetect_avg_ms":  elems.get("det", {}).get("avg_ms", 0),
        "gvadetect_p99_ms":  elems.get("det", {}).get("p99_ms", 0),
        # Top 6 heaviest elements — helps spot regressions per source kind.
        "top_elements":      dict(sorted(
            ((k, v["avg_ms"]) for k, v in elems.items()),
            key=lambda kv: -kv[1])[:6]),
    }


# ── compare mode ────────────────────────────────────────────────────────

def _fmt_row(label: str, *values: str) -> str:
    return "| " + " | ".join([label.ljust(22)] + [v.rjust(14) for v in values]) + " |"


def compare(paths: list[Path]) -> None:
    runs = [json.loads(p.read_text()) for p in paths]
    labels = [f"{r['source_kind']}/{r['device']}" for r in runs]

    print("\n### Live-camera KPI comparison\n")
    print(_fmt_row("KPI", *labels))
    print(_fmt_row("---", *(["---"] * len(labels))))
    for key, human in [
        ("fps_median",       "fps (median)"),
        ("fps_mean",         "fps (mean)"),
        ("fps_min",          "fps (min)"),
        ("frames_produced",  "frames produced"),
        ("e2e_mean_ms",      "e2e latency mean (ms)"),
        ("e2e_p99_ms",       "e2e latency p99 (ms)"),
        ("gvadetect_avg_ms", "gvadetect avg (ms)"),
        ("gvadetect_p99_ms", "gvadetect p99 (ms)"),
    ]:
        print(_fmt_row(human, *(f"{r.get(key, 0)}" for r in runs)))
    print()

    for r, lbl in zip(runs, labels):
        print(f"top elements ({lbl}):")
        for k, v in r["top_elements"].items():
            print(f"  {k:<20} {v:>8.2f} ms")
        print()


# ── entrypoint ──────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source",  choices=["file", "v4l2", "basler"], default="file")
    ap.add_argument("--arg",     default="/videos/polyp_test.mp4",
                    help="source arg (file path / /dev/videoN / Basler serial)")
    ap.add_argument("--device",  default="GPU", choices=["CPU", "GPU", "NPU"])
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--warm",    type=int, default=5,
                    help="warm-up seconds before sampling starts")
    ap.add_argument("--out",     type=Path, default=None,
                    help="write raw result JSON here (for later --compare)")
    ap.add_argument("--compare", nargs="+", type=Path,
                    help="two or more result JSON files → print comparison table")
    args = ap.parse_args()

    if args.compare:
        compare(args.compare)
        return 0

    result = run(args.source, args.arg, args.device, args.seconds, warm_s=args.warm)
    print("\n### Result\n")
    print(json.dumps(result, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
