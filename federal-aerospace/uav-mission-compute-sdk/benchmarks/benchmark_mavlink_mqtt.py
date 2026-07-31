#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
MAVLink→MQTT Path Benchmark
============================
Measures message rate, latency, and jitter for each telemetry topic published
by companion-bridge.  Optionally spawns multiple concurrent subscribers
(--clients N) to observe how fan-out load affects per-client throughput.

Usage:
    python3 benchmark_mavlink_mqtt.py [--duration 30] [--clients 4]
    python3 benchmark_mavlink_mqtt.py --sweep [--sweep-rates 10,25,50,100,200,500]

    # or, if deps are installed via `make deps`:
    .venv/bin/python benchmarks/benchmark_mavlink_mqtt.py [--duration 30]

Passive observation (default):
    Subscribes to uav telemetry and reports observed rate, latency, and
    jitter per topic.  Requires the stack to be running and the uav armed.

Broker stress sweep (--sweep):
    Runs an active publish/subscribe stress test.  For each rate in
    --sweep-rates a dedicated publisher pushes synthetic telemetry messages
    (stamped with bridge_ts_ns) at exactly that Hz for --sweep-duration
    seconds while a subscriber measures what actually arrives.

Bridge stress sweep (--bridge-sweep):
    Real end-to-end stress test of the full PX4 → MAVSDK → companion-bridge
    → MQTT pipeline.  For each rate in --sweep-rates the companion-bridge
    container is recreated with publish rates pinned to that value.

"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

# Local helper for the optional HTML report.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_html import write_html_report  # noqa: E402


MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1884"))
UAV_ID         = os.getenv("UAV_ID", "uav-1")

# Repo root — used by --bridge-sweep to locate docker-compose.yml.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Sentinel for `--html-report` used with no PATH argument: resolved to a
# timestamped filename in the current working directory.
_AUTO_HTML_PATH = object()


def _default_html_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"mavlink_mqtt_benchmark_{stamp}.html"


# --------------------------------------------------------------------------
# System info & deployment health probes (used by the HTML report header)
# --------------------------------------------------------------------------

def _system_info() -> dict:
    import platform
    info: dict = {
        "hostname":   platform.node(),
        "system":     f"{platform.system()} {platform.release()}",
        "machine":    platform.machine(),
        "python":     platform.python_version(),
        "cpu_count":  os.cpu_count(),
        "cpu_model":  platform.processor() or None,
    }
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    info["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except FileNotFoundError:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_kb = int(line.split()[1])
                    info["mem_gb"] = round(mem_kb / 1_048_576, 1)
                    break
    except FileNotFoundError:
        pass
    return info


def _health_probe(host: str, port: int, uav_id: str,
                  timeout_s: float = 3.0, compose_file: Path | None = None) -> dict:
    """Return a snapshot of deployment health suitable for the HTML header."""
    health: dict = {
        "broker": "unknown",
        "telemetry_active": False,
        "telemetry_topics_seen": [],
        "containers": [],
    }

    # 1) Broker reachability + telemetry activity — brief subscribe.
    seen: set[str] = set()
    got_any = threading.Event()

    def _on_msg(client, userdata, msg):
        leaf = msg.topic.rsplit("/", 1)[-1]
        seen.add(leaf)
        got_any.set()

    probe = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"health-probe-{time.time_ns()}",
    )
    probe.on_message = _on_msg
    try:
        probe.connect(host, port, keepalive=10)
        probe.loop_start()
        probe.subscribe(f"uav/{uav_id}/telemetry/#", qos=0)
        health["broker"] = "ok"
        got_any.wait(timeout=timeout_s)
    except Exception as exc:
        health["broker"] = f"error: {exc}"
    finally:
        try:
            probe.loop_stop(); probe.disconnect()
        except Exception:
            pass
    health["telemetry_active"] = bool(seen)
    health["telemetry_topics_seen"] = sorted(seen)

    # 2) docker compose ps (best effort — silently skipped if unavailable).
    cmd = ["docker", "compose"]
    if compose_file is not None:
        cmd += ["-f", str(compose_file)]
    cmd += ["ps", "--format", "json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, list):
                        for x in obj:
                            health["containers"].append(_ctr_row(x))
                    else:
                        health["containers"].append(_ctr_row(obj))
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    return health


def _ctr_row(obj: dict) -> dict:
    return {
        "name":   obj.get("Name") or obj.get("Service") or "?",
        "state":  obj.get("State", ""),
        "status": obj.get("Status", ""),
    }


# --------------------------------------------------------------------------
# Passive observation
# --------------------------------------------------------------------------

@dataclass
class ClientStats:
    idx:       int
    counts:    dict = field(default_factory=lambda: defaultdict(int))
    first_msg: dict = field(default_factory=dict)
    last_msg:  dict = field(default_factory=dict)
    latencies: dict = field(default_factory=lambda: defaultdict(list))
    intervals: dict = field(default_factory=lambda: defaultdict(list))
    lock:      threading.Lock = field(default_factory=threading.Lock)


def _make_on_message(stats: ClientStats):
    """Return an on_message callback that records into *stats*."""
    def _on_message(client, userdata, msg):
        now = time.monotonic()
        parts = msg.topic.split("/")
        leaf = parts[-1] if parts else msg.topic

        with stats.lock:
            stats.counts[leaf] += 1
            if leaf not in stats.first_msg:
                stats.first_msg[leaf] = now
            else:
                gap_ms = (now - stats.last_msg[leaf]) * 1000.0
                stats.intervals[leaf].append(gap_ms)
            stats.last_msg[leaf] = now

        # End-to-end latency uses the *earliest* bridge-side timestamp
        # available so the reported number reflects the full pipeline:
        #   reader_ts_ns  (when the reader consumed the MAVLink message)
        #   → bridge_ts_ns (when publish() stamped it — subject to publish
        #                   timer wait when only bridge_ts_ns is present)
        #   → ISO timestamp (status messages only)
        try:
            payload = json.loads(msg.payload)
            latency_ms = None
            reader_ns = payload.get("reader_ts_ns")
            ts_ns     = payload.get("bridge_ts_ns")
            origin_ns = reader_ns if isinstance(reader_ns, (int, float)) else ts_ns
            if isinstance(origin_ns, (int, float)):
                latency_ms = (time.time_ns() - int(origin_ns)) / 1e6
            else:
                ts_str = payload.get("timestamp")
                if ts_str:
                    import datetime
                    sent = datetime.datetime.fromisoformat(ts_str).timestamp()
                    latency_ms = (time.time() - sent) * 1000.0
            # Clamp to reject clock-skew outliers between containers.
            if latency_ms is not None and -5000 < latency_ms < 60_000:
                with stats.lock:
                    stats.latencies[leaf].append(latency_ms)
        except Exception:
            pass
    return _on_message


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------

def _fmt_row(leaf: str, stats: ClientStats) -> str:
    count = stats.counts[leaf]
    window = stats.last_msg[leaf] - stats.first_msg.get(leaf, stats.last_msg[leaf])
    rate = count / window if window > 0 else 0.0

    intervals = stats.intervals[leaf]
    jitter = statistics.stdev(intervals) if len(intervals) > 1 else 0.0

    lats = stats.latencies[leaf]
    if lats:
        lat_mean = statistics.mean(lats)
        lat_p99  = sorted(lats)[int(len(lats) * 0.99)]
        lat_str  = f"{lat_mean:>10.1f}   {lat_p99:>10.1f}"
    else:
        lat_str  = f"{'n/a':>10}   {'n/a':>10}"

    return (f"  {leaf:<20} {count:>6}  {rate:>8.1f}  {lat_str}  {jitter:>10.1f}")


def _print_topic_table(stats: ClientStats, elapsed: float, label: str) -> None:
    W = 78
    print(f"\n  {label}")
    print(f"  {'─'*W}")
    print(f"  {'Topic':<20} {'Msgs':>6}  {'Rate (Hz)':>8}  "
          f"{'Avg Lat (ms)':>10}   {'P99 Lat (ms)':>10}  {'Jitter (ms)':>10}")
    print(f"  {'─'*W}")
    if not stats.counts:
        print("    No messages received — is the stack running and uav armed?")
    else:
        for leaf in sorted(stats.counts, key=lambda k: -stats.counts[k]):
            print(_fmt_row(leaf, stats))
    total = sum(stats.counts.values())
    overall_rate = total / elapsed if elapsed > 0 else 0.0
    print(f"  {'─'*W}")
    print(f"  {'TOTAL':<20} {total:>6}  {overall_rate:>8.1f}")


# --------------------------------------------------------------------------
# Broker stress sweep
# --------------------------------------------------------------------------

@dataclass
class _StressTierResult:
    hz:        float
    published: int
    received:  int
    elapsed_s: float
    latencies: list
    intervals: list


def _run_stress_tier(
    host: str,
    port: int,
    hz: float,
    duration_s: float,
    uav_id: str,
) -> _StressTierResult:
    # Publish synthetic telemetry at *hz* and measure what the subscriber sees.
    topic    = f"uav/{uav_id}/telemetry/stress"
    interval = 1.0 / hz

    received_count = 0
    latencies: list[float] = []
    intervals: list[float] = []
    last_mono: list = [None]
    lock       = threading.Lock()
    subscribed = threading.Event()

    def _on_sub_connect(client, userdata, flags, reason_code, properties):
        client.subscribe(topic, qos=0)

    def _on_sub_subscribe(client, userdata, mid, reason_codes, properties):
        subscribed.set()

    def _on_message(client, userdata, msg):
        nonlocal received_count
        now_ns   = time.time_ns()
        now_mono = time.monotonic()
        lat_ms   = None
        try:
            ts_ns = json.loads(msg.payload).get("bridge_ts_ns")
            if isinstance(ts_ns, (int, float)):
                lat_ms = (now_ns - int(ts_ns)) / 1e6
        except Exception:
            pass
        with lock:
            received_count += 1
            if last_mono[0] is not None:
                intervals.append((now_mono - last_mono[0]) * 1000.0)
            last_mono[0] = now_mono
            if lat_ms is not None and -100 < lat_ms < 60_000:
                latencies.append(lat_ms)

    sub = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"stress-sub-{hz:.0f}hz",
    )
    sub.on_connect   = _on_sub_connect
    sub.on_subscribe = _on_sub_subscribe
    sub.on_message   = _on_message
    sub.connect(host, port, keepalive=60)
    sub.loop_start()
    if not subscribed.wait(timeout=5.0):
        sub.loop_stop(); sub.disconnect()
        raise RuntimeError(f"Subscriber did not subscribe within 5 s at {host}:{port}")

    pub = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"stress-pub-{hz:.0f}hz",
    )
    pub.connect(host, port, keepalive=60)
    pub.loop_start()

    # Absolute-deadline publish loop — avoids cumulative drift at high rates.
    published = 0
    start     = time.monotonic()
    while time.monotonic() - start < duration_s:
        next_pub = start + published * interval
        now      = time.monotonic()
        gap      = next_pub - now
        if gap > 0.001:
            time.sleep(gap * 0.8)
            continue
        if gap > 0:
            while time.monotonic() < next_pub:
                pass
        pub.publish(
            topic,
            json.dumps({"bridge_ts_ns": time.time_ns(), "seq": published}).encode(),
            qos=0,
        )
        published += 1

    actual_elapsed = time.monotonic() - start
    # Drain in-flight messages before tearing down.
    time.sleep(min(0.5, interval * 10))

    pub.loop_stop(); pub.disconnect()
    sub.loop_stop(); sub.disconnect()

    with lock:
        return _StressTierResult(
            hz=hz,
            published=published,
            received=received_count,
            elapsed_s=actual_elapsed,
            latencies=list(latencies),
            intervals=list(intervals),
        )


_DROP_WARN_PCT = 2.0


def _print_stress_table(
    results: list[_StressTierResult], duration_s: float, host: str, port: int
) -> None:
    W = 90
    print(f"\n{'─'*80}")
    print(f"  MQTT Broker Stress Sweep  "
          f"({duration_s:.0f}s per tier · QoS 0 · broker {host}:{port})")
    print(f"  Payload: JSON with bridge_ts_ns for end-to-end latency measurement")
    print(f"{'─'*80}")
    hdr1 = (f"  {'Config':>11}  {'Published':>10}  {'Received':>10}  {'Drop':>6}  "
            f"{'Eff. Rate':>10}  {'Avg Lat':>9}  {'P99 Lat':>9}  {'Jitter':>9}")
    hdr2 = (f"  {'(Hz)':>11}  {'':>10}  {'':>10}  {'%':>6}  "
            f"{'(Hz)':>10}  {'(ms)':>9}  {'(ms)':>9}  {'(ms)':>9}")
    print(hdr1)
    print(hdr2)
    print(f"  {'─'*W}")

    first_bad_hz: float | None = None
    for r in results:
        drop_pct = (1.0 - r.received / r.published) * 100 if r.published else 0.0
        eff_rate = r.received / r.elapsed_s if r.elapsed_s > 0 else 0.0
        if r.latencies:
            avg_lat = statistics.mean(r.latencies)
            p99_lat = sorted(r.latencies)[int(len(r.latencies) * 0.99)]
            lat_str = f"{avg_lat:>9.2f}  {p99_lat:>9.2f}"
        else:
            lat_str = f"{'n/a':>9}  {'n/a':>9}"
        jitter = statistics.stdev(r.intervals) if len(r.intervals) > 1 else 0.0
        flag   = " ⚠" if drop_pct >= _DROP_WARN_PCT else ""
        if drop_pct >= _DROP_WARN_PCT and first_bad_hz is None:
            first_bad_hz = r.hz
        print(f"  {r.hz:>11.1f}  {r.published:>10}  {r.received:>10}  "
              f"{drop_pct:>5.1f}%  {eff_rate:>10.1f}  {lat_str}  {jitter:>9.2f}{flag}")

    print(f"  {'─'*W}")
    if first_bad_hz is not None:
        print(f"  ⚠  Drop ≥ {_DROP_WARN_PCT:.0f}% first seen at {first_bad_hz:.0f} Hz — "
              f"broker saturates above this point.")
    else:
        print(f"  All tiers clean (drop < {_DROP_WARN_PCT:.0f}%). "
              f"Broker handled up to {results[-1].hz:.0f} Hz without saturation.")
    print(f"  Note: companion-bridge caps the MAVLink→MQTT path at "
          f"20 Hz (attitude/velocity) and 10 Hz (position).\n")


# --------------------------------------------------------------------------
# Bridge stress sweep
# --------------------------------------------------------------------------

# Topics whose RATE_<LEAF>_HZ env var is bumped each tier.
BRIDGE_STRESS_TOPICS = ("attitude", "velocity", "position", "gps")

# Observed but not bumped — no RATE_<LEAF>_HZ knob exists.  `status` is
# change-triggered, so its rate reflects state churn, not throughput.
BRIDGE_OBSERVE_EXTRAS = ("status",)

BRIDGE_REPORT_TOPICS = BRIDGE_STRESS_TOPICS + BRIDGE_OBSERVE_EXTRAS


@dataclass
class _BridgeTierResult:
    hz:            float
    per_topic:     dict   # leaf -> (count, obs_hz, avg_lat, p99_lat, jitter)
    total_received: int
    elapsed_s:     float


def _recreate_companion_bridge(env_overrides: dict, compose_file: Path) -> None:
    """Force-recreate the companion-bridge container with new env vars."""
    env = os.environ.copy()
    env.update(env_overrides)
    cmd = [
        "docker", "compose", "-f", str(compose_file),
        "up", "-d", "--no-deps", "--force-recreate", "companion-bridge",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"docker compose failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _wait_for_bridge(host: str, port: int, uav_id: str, timeout_s: float) -> bool:
    """Block until the bridge publishes at least one telemetry message."""
    got_msg = threading.Event()

    def _on_msg(client, userdata, msg):
        got_msg.set()

    w = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"bridge-sweep-wait-{time.time_ns()}",
    )
    w.on_message = _on_msg
    w.connect(host, port, keepalive=30)
    w.subscribe(f"uav/{uav_id}/telemetry/+", qos=0)
    w.loop_start()
    ok = got_msg.wait(timeout=timeout_s)
    w.loop_stop(); w.disconnect()
    return ok


def _run_bridge_tier(
    host: str, port: int, hz: float, duration_s: float,
    uav_id: str, compose_file: Path, restart_wait_s: float,
) -> _BridgeTierResult:
    # Recreate the bridge with BRIDGE_STRESS_TOPICS capped at *hz*.
    env_overrides = {
        f"RATE_{t.upper()}_HZ": str(hz) for t in BRIDGE_STRESS_TOPICS
    }
    _recreate_companion_bridge(env_overrides, compose_file)

    if not _wait_for_bridge(host, port, uav_id, restart_wait_s):
        raise RuntimeError(
            f"Bridge did not publish telemetry within {restart_wait_s}s "
            f"after restart — is PX4 running and the uav armed?"
        )

    stats = ClientStats(idx=0)
    sub = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"bridge-sweep-sub-{hz:.0f}hz",
    )
    sub.on_message = _make_on_message(stats)
    sub.connect(host, port, keepalive=60)
    sub.subscribe(f"uav/{uav_id}/telemetry/#", qos=0)
    sub.loop_start()

    start = time.monotonic()
    time.sleep(duration_s)
    elapsed = time.monotonic() - start

    sub.loop_stop(); sub.disconnect()

    per_topic: dict = {}
    for leaf in BRIDGE_REPORT_TOPICS:
        count   = stats.counts.get(leaf, 0)
        window  = stats.last_msg.get(leaf, 0) - stats.first_msg.get(leaf, 0)
        obs_hz  = count / window if window > 0 else 0.0
        lats    = stats.latencies.get(leaf, [])
        avg_lat = statistics.mean(lats) if lats else float("nan")
        p99_lat = sorted(lats)[int(len(lats) * 0.99)] if lats else float("nan")
        gaps    = stats.intervals.get(leaf, [])
        jitter  = statistics.stdev(gaps) if len(gaps) > 1 else 0.0
        per_topic[leaf] = (count, obs_hz, avg_lat, p99_lat, jitter)

    return _BridgeTierResult(
        hz=hz,
        per_topic=per_topic,
        total_received=sum(stats.counts.values()),
        elapsed_s=elapsed,
    )


def _print_bridge_table(
    results: list[_BridgeTierResult], duration_s: float, host: str, port: int
) -> None:
    W = 82
    print(f"\n{'─'*80}")
    print(f"  Companion-Bridge Stress Sweep  "
          f"({duration_s:.0f}s per tier · broker {host}:{port})")
    print(f"  Path: PX4 → MAVSDK → companion-bridge → MQTT (full pipeline)")
    print(f"{'─'*80}")
    print(f"  {'Cap':>6}  {'Topic':<10}  {'Rcvd':>6}  {'Observed Hz':>8}  "
          f"{'Achieved':>9}  {'Avg Lat':>9}  {'P99 Lat':>9}")
    print(f"  {'(Hz)':>6}  {'':<10}  {'':>6}  {'':>8}  "
          f"{'vs cap':>9}  {'(ms)':>9}  {'(ms)':>9}")
    print(f"  {'─'*W}")

    for r in results:
        for leaf in BRIDGE_REPORT_TOPICS:
            count, obs_hz, avg_lat, p99_lat, _jitter = r.per_topic.get(
                leaf, (0, 0.0, float("nan"), float("nan"), 0.0)
            )
            is_capped = leaf in BRIDGE_STRESS_TOPICS
            if is_capped:
                achieved = obs_hz / r.hz if r.hz > 0 else 0.0
                ach_str = f"{achieved*100:>8.0f}%"
            else:
                ach_str = f"{'—':>9}"
            lat_str = (f"{avg_lat:>9.2f}  {p99_lat:>9.2f}"
                       if count else f"{'n/a':>9}  {'n/a':>9}")
            print(f"  {r.hz:>6.0f}  {leaf:<10}  {count:>6}  {obs_hz:>8.1f}  "
                  f"{ach_str}  {lat_str}")
        print(f"  {'·'*W}")

    print(f"  {'─'*W}")
    print(f"  Latency = recv_ts − reader_ts_ns "
          f"(full path from MAVSDK read to subscriber receive).\n")


# --------------------------------------------------------------------------
# Client scaling sweep
# --------------------------------------------------------------------------

@dataclass
class _ClientSweepTier:
    n_clients: int
    duration_s: float
    per_client_counts: list
    per_client_lats:   list
    all_lats:          list


def _run_client_sweep_tier(
    host: str, port: int, uav_id: str, n: int, duration_s: float,
) -> _ClientSweepTier:
    all_stats = [ClientStats(idx=i) for i in range(n)]
    clients = []
    try:
        for st in all_stats:
            c = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"scale-{n}-{st.idx}",
            )
            c.on_message = _make_on_message(st)
            c.connect(host, port, keepalive=60)
            c.subscribe(f"uav/{uav_id}/telemetry/#", qos=0)
            c.loop_start()
            clients.append(c)
        start = time.monotonic()
        time.sleep(duration_s)
        elapsed = time.monotonic() - start
    finally:
        for c in clients:
            try:
                c.loop_stop(); c.disconnect()
            except Exception:
                pass

    per_counts = [sum(s.counts.values()) for s in all_stats]
    per_lats: list[float | None] = []
    all_lats: list[float] = []
    for s in all_stats:
        flat = [lat for lats in s.latencies.values() for lat in lats]
        per_lats.append(statistics.mean(flat) if flat else None)
        all_lats.extend(flat)
    return _ClientSweepTier(
        n_clients=n,
        duration_s=elapsed,
        per_client_counts=per_counts,
        per_client_lats=per_lats,
        all_lats=all_lats,
    )


def _print_client_sweep_table(tiers: list[_ClientSweepTier]) -> None:
    W = 74
    print(f"\n{'─'*80}")
    print(f"  Client Scaling Sweep  ({len(tiers)} tier(s))")
    print(f"{'─'*80}")
    print(f"  {'N':>5}  {'Per-client Hz':>14}  {'Aggregate Hz':>13}  "
          f"{'CV %':>6}  {'Avg Lat ms':>11}")
    print(f"  {'─'*W}")
    for t in tiers:
        rates = [c / t.duration_s if t.duration_s > 0 else 0.0
                 for c in t.per_client_counts]
        mean_rate = statistics.mean(rates) if rates else 0.0
        agg = sum(rates)
        cv = (statistics.stdev(rates) / mean_rate * 100
              if len(rates) > 1 and mean_rate else 0.0)
        avg_lat = statistics.mean(t.all_lats) if t.all_lats else float("nan")
        lat_str = f"{avg_lat:>11.2f}" if t.all_lats else f"{'n/a':>11}"
        print(f"  {t.n_clients:>5}  {mean_rate:>14.2f}  {agg:>13.2f}  "
              f"{cv:>5.1f}  {lat_str}")
    print(f"  {'─'*W}\n")


def _client_scaling_report_dict(tiers: list[_ClientSweepTier]) -> dict:
    out_tiers = []
    for t in tiers:
        rates = [c / t.duration_s if t.duration_s > 0 else 0.0
                 for c in t.per_client_counts]
        mean_rate = statistics.mean(rates) if rates else 0.0
        cv = (statistics.stdev(rates) / mean_rate * 100
              if len(rates) > 1 and mean_rate else 0.0)
        avg_lat = statistics.mean(t.all_lats) if t.all_lats else None
        p99_lat = (sorted(t.all_lats)[int(len(t.all_lats) * 0.99)]
                   if t.all_lats else None)
        out_tiers.append({
            "n_clients": t.n_clients,
            "mean_rate": mean_rate,
            "agg_rate":  sum(rates),
            "cv":        cv,
            "avg_lat":   avg_lat,
            "p99_lat":   p99_lat,
        })
    # Duration of the last tier serves as a representative window value.
    duration = tiers[-1].duration_s if tiers else 0.0
    return {"duration_s": duration, "tiers": out_tiers}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Benchmark MAVLink→MQTT path")
    parser.add_argument("--duration", type=int, default=20,
                        help="Measurement window in seconds (default: 20)")
    parser.add_argument("--host", default=MQTT_BROKER_HOST)
    parser.add_argument("--port", type=int, default=MQTT_BROKER_PORT)
    parser.add_argument("--clients", type=int, default=1,
                        help="Number of concurrent MQTT subscribers (default: 1). "
                             "Increase to test broker fan-out under load.")
    parser.add_argument("--sweep", action="store_true",
                        help="Run an active broker stress sweep instead of (or after) "
                             "passive observation.  A publisher injects synthetic "
                             "telemetry at each rate in --sweep-rates while a "
                             "subscriber measures throughput, drop%%, and latency. "
                             "Only the MQTT broker needs to be running.")
    parser.add_argument("--sweep-rates", default="10,25,50,100,200,500",
                        metavar="HZ_LIST",
                        help="Comma-separated publish rates (Hz) for the stress sweep "
                             "(default: 10,25,50,100,200,500).")
    parser.add_argument("--sweep-duration", type=float, default=10.0,
                        metavar="SECS",
                        help="Measurement window per tier in seconds (default: 10).")
    parser.add_argument("--bridge-sweep", action="store_true",
                        help="Real end-to-end stress: for each rate in --sweep-rates, "
                             "recreate the companion-bridge container with "
                             "RATE_ATTITUDE_HZ / RATE_VELOCITY_HZ / RATE_POSITION_HZ / "
                             "RATE_GPS_HZ set to that value, wait for reconnect, and "
                             "measure what PX4 actually delivers.  Requires PX4 + "
                             "broker running and `docker compose` on PATH.  UAV "
                             "should be armed or providing telemetry.")
    parser.add_argument("--client-sweep", action="store_true",
                        help="Scaling sweep: run passive observation at each client "
                             "count in --client-sweep-counts (up to 100).  Reports "
                             "per-client mean rate, aggregate rate, rate CV, and "
                             "avg / P99 latency at each tier.")
    parser.add_argument("--client-sweep-counts",
                        default="1,2,5,10,25,50,100",
                        metavar="N_LIST",
                        help="Comma-separated client counts for --client-sweep "
                             "(default: 1,2,5,10,25,50,100).")
    parser.add_argument("--compose-file", default=str(REPO_ROOT / "docker-compose.yml"),
                        help="Path to docker-compose.yml used by --bridge-sweep "
                             f"(default: {REPO_ROOT / 'docker-compose.yml'}).")
    parser.add_argument("--restart-wait", type=float, default=30.0,
                        metavar="SECS",
                        help="Max seconds to wait after bridge recreate for the first "
                             "telemetry message (default: 30).")
    parser.add_argument("--html-report", nargs="?", default=None,
                        const=_AUTO_HTML_PATH, metavar="PATH",
                        help="If set, write a self-contained HTML report with "
                             "tables and Chart.js charts covering every mode "
                             "that ran in this invocation.  PATH is optional; "
                             "with no value the report is written to "
                             "./mavlink_mqtt_benchmark_<UTC timestamp>.html "
                             "in the current directory.")
    args = parser.parse_args()

    if args.html_report is _AUTO_HTML_PATH:
        args.html_report = str(Path.cwd() / _default_html_filename())

    # Structured payloads for the HTML report; each mode fills its own key.
    report_meta: dict = {
        "generated_at": _iso_now(),
        "host": args.host,
        "port": args.port,
        "uav_id": UAV_ID,
        "cli_args": sys.argv[1:],
    }
    report_system: dict | None = None
    report_health: dict | None = None
    report_client_scaling: dict | None = None
    report_broker: dict | None = None
    report_bridge: dict | None = None
    if args.html_report:
        # System info + health snapshot are cheap; grab them once up front so
        # they reflect the pre-benchmark state, not whatever the bridge sweep
        # left behind.
        report_system = _system_info()
        report_health = _health_probe(
            args.host, args.port, UAV_ID,
            compose_file=Path(args.compose_file),
        )

    # ── Client scaling sweep ──────────────────────────────────────────────
    if args.client_sweep:
        counts = sorted({
            int(n.strip()) for n in args.client_sweep_counts.split(",")
            if n.strip()
        })
        print(f"\n{'─'*80}")
        print(f"  Client scaling sweep: {len(counts)} tier(s) "
              f"× {args.sweep_duration:.0f}s each")
        print(f"  Counts: {counts}")
        print(f"{'─'*80}")
        client_tiers: list[_ClientSweepTier] = []
        for n in counts:
            print(f"  → N={n} …", end="", flush=True)
            try:
                t = _run_client_sweep_tier(
                    args.host, args.port, UAV_ID, n, args.sweep_duration,
                )
                client_tiers.append(t)
                total = sum(t.per_client_counts)
                print(f"  received={total}  "
                      f"per-client≈{total/n if n else 0:.1f} msgs")
            except Exception as exc:
                print(f" FAILED: {exc}", file=sys.stderr)
        if client_tiers:
            _print_client_sweep_table(client_tiers)
            report_client_scaling = _client_scaling_report_dict(client_tiers)

    # ── Bridge stress sweep ───────────────────────────────────────────────
    if args.bridge_sweep:
        sweep_rates = sorted({
            float(r.strip()) for r in args.sweep_rates.split(",") if r.strip()
        })
        compose_file = Path(args.compose_file).resolve()
        if not compose_file.exists():
            print(f"ERROR: compose file not found: {compose_file}", file=sys.stderr)
            sys.exit(1)
        print(f"\n{'─'*80}")
        print(f"  Bridge stress sweep: {len(sweep_rates)} tier(s) "
              f"× {args.sweep_duration:.0f}s each")
        print(f"  Compose file: {compose_file}")
        print(f"  Will bump: {', '.join('RATE_' + t.upper() + '_HZ' for t in BRIDGE_STRESS_TOPICS)}")
        print(f"{'─'*80}")
        bridge_results: list[_BridgeTierResult] = []
        try:
            for hz in sweep_rates:
                print(f"  → cap={hz:.0f} Hz  (recreating companion-bridge …)",
                      flush=True)
                try:
                    r = _run_bridge_tier(
                        args.host, args.port, hz, args.sweep_duration,
                        UAV_ID, compose_file, args.restart_wait,
                    )
                    bridge_results.append(r)
                    summary = "  ".join(
                        f"{leaf}={r.per_topic[leaf][1]:.1f}Hz"
                        for leaf in BRIDGE_STRESS_TOPICS
                    )
                    print(f"     ✓ {summary}")
                except Exception as exc:
                    print(f"     FAILED: {exc}", file=sys.stderr)
        finally:
            # Restore bridge to default caps so we don't leave the stack in
            # a stressed state for other users.
            print(f"\n  Restoring companion-bridge to default rate caps …")
            try:
                _recreate_companion_bridge({}, compose_file)
            except Exception as exc:
                print(f"  WARNING: could not restore bridge: {exc}",
                      file=sys.stderr)
        if bridge_results:
            _print_bridge_table(bridge_results, args.sweep_duration,
                                args.host, args.port)
            report_bridge = {
                "duration_s": args.sweep_duration,
                "tiers": [
                    {
                        "hz": r.hz,
                        "topics": {
                            leaf: {
                                "count":         data[0],
                                "obs_hz":        data[1],
                                "avg_lat":       data[2],
                                "p99_lat":       data[3],
                                "jitter":        data[4],
                                "achieved_pct": (data[1] / r.hz * 100.0
                                                 if r.hz > 0 and leaf in BRIDGE_STRESS_TOPICS
                                                 else None),
                            }
                            for leaf, data in r.per_topic.items()
                        },
                    }
                    for r in bridge_results
                ],
            }
        # If user only asked for bridge sweep, exit here.
        if not args.sweep and not args.client_sweep:
            if args.html_report:
                _emit_html(args.html_report, report_meta, report_system,
                           report_health, report_client_scaling,
                           report_broker, report_bridge)
            return

    # If --client-sweep is set we skip the one-shot passive observation
    # (client-sweep already covers that at multiple N values).
    if args.client_sweep:
        if args.sweep:
            _run_broker_sweep_and_report(args, report_meta, report_system,
                                          report_health, report_client_scaling,
                                          report_bridge)
        elif args.html_report:
            _emit_html(args.html_report, report_meta, report_system,
                       report_health, report_client_scaling,
                       report_broker, report_bridge)
        return

    n = max(1, args.clients)
    all_stats = [ClientStats(idx=i) for i in range(n)]

    print(f"Connecting {n} client(s) to MQTT broker {args.host}:{args.port} …")

    clients = []
    for stats in all_stats:
        c = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"mavlink-bench-{stats.idx}",
        )
        c.on_message = _make_on_message(stats)
        try:
            c.connect(args.host, args.port, keepalive=60)
        except Exception as e:
            print(f"ERROR: Could not connect client {stats.idx}: {e}", file=sys.stderr)
            sys.exit(1)
        c.subscribe(f"uav/{UAV_ID}/telemetry/#", qos=0)
        c.loop_start()
        clients.append(c)

    start_wall = time.monotonic()
    print(f"Listening for {args.duration}s on uav/{UAV_ID}/telemetry/#\n")

    try:
        for remaining in range(args.duration, 0, -1):
            print(f"\r  {remaining:3d}s remaining …", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    for c in clients:
        c.loop_stop()
        c.disconnect()
    elapsed = time.monotonic() - start_wall

    print(f"\r\n{'─'*80}")
    print(f"  Duration: {elapsed:.1f}s   Broker: {args.host}:{args.port}   Clients: {n}")
    print(f"{'─'*80}")

    # Per-client topic tables
    for stats in all_stats:
        label = f"Client {stats.idx}" if n > 1 else "Results"
        _print_topic_table(stats, elapsed, label)

    # Scaling summary (multi-client only)
    if n > 1:
        W = 78
        print(f"\n{'─'*80}")
        print(f"  Scaling summary  ({n} concurrent subscribers)")
        print(f"  {'─'*W}")
        print(f"  {'Client':>8}  {'Total Msgs':>10}  {'Rate (Hz)':>10}  {'Avg Lat (ms)':>13}")
        print(f"  {'─'*W}")
        per_client_rates: list[float] = []
        per_client_lats:  list[float] = []
        for stats in all_stats:
            total = sum(stats.counts.values())
            rate  = total / elapsed if elapsed > 0 else 0.0
            all_lats = [lat for lats in stats.latencies.values() for lat in lats]
            avg_lat = statistics.mean(all_lats) if all_lats else float("nan")
            per_client_rates.append(rate)
            per_client_lats.append(avg_lat)
            lat_str = f"{avg_lat:>13.1f}" if all_lats else f"{'n/a':>13}"
            print(f"  {stats.idx:>8}  {total:>10}  {rate:>10.1f}  {lat_str}")
        print(f"  {'─'*W}")
        valid_rates = [r for r in per_client_rates if r > 0]
        if valid_rates:
            cv = (statistics.stdev(valid_rates) / statistics.mean(valid_rates) * 100
                  if len(valid_rates) > 1 else 0.0)
            print(f"\n  Rate spread across clients: "
                  f"min={min(valid_rates):.1f}  max={max(valid_rates):.1f}  CV={cv:.1f}%")
            if cv > 10:
                print(f"  ⚠  High rate variance (CV={cv:.1f}%) — "
                      "broker may be struggling to fan-out evenly")
        print()

    # Flag topics that appear to be running well above their expected cap.
    ref = all_stats[0]
    EXPECTED_CAPS = {"attitude": 25, "velocity": 25, "position": 15}
    warned = False
    for topic, cap_hz in EXPECTED_CAPS.items():
        if topic in ref.counts:
            window = ref.last_msg[topic] - ref.first_msg.get(topic, ref.last_msg[topic])
            rate = ref.counts[topic] / window if window > 0 else 0.0
            if rate > cap_hz * 1.5:
                if not warned:
                    print("  WARNINGS:")
                    warned = True
                print(f"  ⚠  {topic} rate {rate:.0f}Hz exceeds expected cap "
                      f"{cap_hz}Hz — check RATE_{topic.upper()}_HZ env var")
    if warned:
        print()

    if args.sweep:
        sweep_rates = sorted({
            float(r.strip()) for r in args.sweep_rates.split(",") if r.strip()
        })
        print(f"\n{'─'*80}")
        print(f"  Starting broker stress sweep: {len(sweep_rates)} tier(s), "
              f"{args.sweep_duration:.0f}s each …")
        results: list[_StressTierResult] = []
        for hz in sweep_rates:
            print(f"  → {hz:.0f} Hz … ", end="", flush=True)
            try:
                r = _run_stress_tier(
                    args.host, args.port, hz, args.sweep_duration, UAV_ID
                )
                results.append(r)
                drop = (1 - r.received / r.published) * 100 if r.published else 0
                print(f"published={r.published}  received={r.received}  "
                      f"drop={drop:.1f}%")
            except Exception as exc:
                print(f"FAILED: {exc}", file=sys.stderr)
        _print_stress_table(results, args.sweep_duration, args.host, args.port)
        report_broker = _broker_report_dict(results, args.sweep_duration)

    if args.html_report:
        _emit_html(args.html_report, report_meta, report_system,
                   report_health, report_client_scaling,
                   report_broker, report_bridge)


# --------------------------------------------------------------------------
# HTML report snapshot helpers
# --------------------------------------------------------------------------

def _broker_report_dict(results, duration_s):
    tiers = []
    for r in results:
        drop_pct = (1.0 - r.received / r.published) * 100 if r.published else 0.0
        eff_rate = r.received / r.elapsed_s if r.elapsed_s > 0 else 0.0
        avg_lat  = statistics.mean(r.latencies) if r.latencies else None
        p99_lat  = (sorted(r.latencies)[int(len(r.latencies) * 0.99)]
                    if r.latencies else None)
        jitter   = statistics.stdev(r.intervals) if len(r.intervals) > 1 else 0.0
        tiers.append({
            "hz":        r.hz,
            "published": r.published,
            "received":  r.received,
            "drop_pct":  drop_pct,
            "eff_rate":  eff_rate,
            "avg_lat":   avg_lat,
            "p99_lat":   p99_lat,
            "jitter":    jitter,
        })
    return {"duration_s": duration_s, "tiers": tiers}


def _emit_html(path, meta, system, health, client_scaling, broker, bridge):
    try:
        write_html_report(
            Path(path),
            meta=meta, system=system, health=health,
            client_scaling=client_scaling,
            broker=broker, bridge=bridge,
        )
        print(f"\n  HTML report written to {path}")
    except Exception as exc:
        print(f"\n  WARNING: could not write HTML report: {exc}",
              file=sys.stderr)


def _run_broker_sweep_and_report(args, meta, system, health,
                                  client_scaling, bridge):
    """Run the broker stress sweep and (optionally) emit the HTML report."""
    sweep_rates = sorted({
        float(r.strip()) for r in args.sweep_rates.split(",") if r.strip()
    })
    print(f"\n{'─'*80}")
    print(f"  Starting broker stress sweep: {len(sweep_rates)} tier(s), "
          f"{args.sweep_duration:.0f}s each …")
    results: list[_StressTierResult] = []
    for hz in sweep_rates:
        print(f"  → {hz:.0f} Hz … ", end="", flush=True)
        try:
            r = _run_stress_tier(
                args.host, args.port, hz, args.sweep_duration, UAV_ID
            )
            results.append(r)
            drop = (1 - r.received / r.published) * 100 if r.published else 0
            print(f"published={r.published}  received={r.received}  "
                  f"drop={drop:.1f}%")
        except Exception as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
    _print_stress_table(results, args.sweep_duration, args.host, args.port)
    broker_dict = _broker_report_dict(results, args.sweep_duration) if results else None
    if args.html_report:
        _emit_html(args.html_report, meta, system, health,
                   client_scaling, broker_dict, bridge)


if __name__ == "__main__":
    main()
