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
    python3 benchmark_mavlink_mqtt.py --bridge-sweep [--sweep-rates 20,50,100,200]

    # or, if deps are installed via `make deps`:
    .venv/bin/python benchmarks/benchmark_mavlink_mqtt.py [--duration 30]

Passive observation (default):
    Subscribes to uav telemetry and reports observed rate, latency, and
    jitter per topic.  Requires the stack to be running and the uav armed.

Bridge stress sweep (--bridge-sweep):
    Real end-to-end stress test of the full PX4 → MAVSDK → companion-bridge
    → MQTT pipeline.  For each rate in --sweep-rates the companion-bridge
    container is recreated with publish rates pinned to that value.

"""

import argparse
import json
import os
import math
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
RESOURCE_CONTAINERS = ("companion-bridge", "mqtt-broker")
RESOURCE_SAMPLING_INTERVAL_S = 1.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_pct(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def _parse_size_to_mib(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip().lower()
    units = [
        ("tib", 1024.0 * 1024.0),
        ("tb", 1024.0 * 1024.0),
        ("gib", 1024.0),
        ("gb", 1024.0),
        ("mib", 1.0),
        ("mb", 1.0),
        ("kib", 1.0 / 1024.0),
        ("kb", 1.0 / 1024.0),
        ("b", 1.0 / (1024.0 * 1024.0)),
    ]
    for suffix, factor in units:
        if text.endswith(suffix):
            try:
                return float(text[:-len(suffix)].strip()) * factor
            except ValueError:
                return None
    return None


def _safe_mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _safe_max(values: list[float]) -> float | None:
    return max(values) if values else None


def _resource_summary(samples: list[dict]) -> dict:
    cpu = [sample["cpu_pct"] for sample in samples if sample.get("cpu_pct") is not None]
    mem_pct = [sample["mem_pct"] for sample in samples if sample.get("mem_pct") is not None]
    mem_mib = [sample["mem_mib"] for sample in samples if sample.get("mem_mib") is not None]
    return {
        "samples": len(samples),
        "avg_cpu_pct": _safe_mean(cpu),
        "peak_cpu_pct": _safe_max(cpu),
        "avg_mem_pct": _safe_mean(mem_pct),
        "peak_mem_pct": _safe_max(mem_pct),
        "avg_mem_mib": _safe_mean(mem_mib),
        "peak_mem_mib": _safe_max(mem_mib),
    }


class _DockerStatsSampler:
    def __init__(self, containers: tuple[str, ...], interval_s: float = RESOURCE_SAMPLING_INTERVAL_S):
        self.containers = containers
        self.interval_s = interval_s
        self._samples: dict[str, list[dict]] = {name: [] for name in containers}
        self._errors: list[str] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> dict:
        self._stop.set()
        self._thread.join(timeout=self.interval_s + 5.0)
        resources = {
            name: _resource_summary(samples)
            for name, samples in self._samples.items()
        }
        if self._errors:
            resources["_errors"] = list(self._errors)
        return resources

    def _run(self) -> None:
        while not self._stop.is_set():
            self._capture_once()
            if self._stop.wait(self.interval_s):
                break

    def _capture_once(self) -> None:
        cmd = [
            "docker", "stats", "--no-stream",
            "--format", "{{json .}}",
            *self.containers,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            self._errors.append("docker not found on PATH")
            self._stop.set()
            return
        except subprocess.TimeoutExpired:
            self._errors.append("docker stats timed out")
            return

        if result.returncode != 0:
            stderr = result.stderr.strip() or f"docker stats rc={result.returncode}"
            self._errors.append(stderr)
            return

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                self._errors.append(f"unparseable docker stats row: {line[:120]}")
                continue

            name = row.get("Name")
            if name not in self._samples:
                continue
            mem_usage = row.get("MemUsage", "").split("/", 1)[0].strip()
            self._samples[name].append({
                "cpu_pct": _parse_pct(row.get("CPUPerc")),
                "mem_pct": _parse_pct(row.get("MemPerc")),
                "mem_mib": _parse_size_to_mib(mem_usage),
            })


def _measure_with_resources(duration_s: float, measure) -> tuple[object, dict]:
    interval = max(0.5, min(RESOURCE_SAMPLING_INTERVAL_S, duration_s / 4.0 if duration_s > 0 else RESOURCE_SAMPLING_INTERVAL_S))
    sampler = _DockerStatsSampler(RESOURCE_CONTAINERS, interval_s=interval)
    sampler.start()
    try:
        result = measure()
    finally:
        resources = sampler.stop()
    return result, resources


def _fmt_metric(value: float | None, digits: int = 2, empty: str = "n/a") -> str:
    if value is None:
        return empty
    if isinstance(value, float) and math.isnan(value):
        return empty
    return f"{value:.{digits}f}"


def _print_resource_table(label: str, tiers: list[dict], tier_label: str, tier_fmt) -> None:
    if not tiers:
        return
    W = 112
    print(f"\n{'─'*80}")
    print(f"  {label}")
    print(f"  {'─'*W}")
    print(f"  {tier_label:>10}  {'Container':<18}  {'CPU Avg %':>9}  {'CPU Peak %':>10}  {'Mem Avg %':>9}  {'Mem Peak %':>10}  {'Mem Avg MiB':>11}  {'Mem Peak MiB':>12}")
    print(f"  {'─'*W}")
    for tier in tiers:
        key = tier_fmt(tier)
        for container in RESOURCE_CONTAINERS:
            summary = tier.get("resources", {}).get(container, {})
            print(
                f"  {key:>10}  {container:<18}  "
                f"{_fmt_metric(summary.get('avg_cpu_pct')):>9}  "
                f"{_fmt_metric(summary.get('peak_cpu_pct')):>10}  "
                f"{_fmt_metric(summary.get('avg_mem_pct')):>9}  "
                f"{_fmt_metric(summary.get('peak_mem_pct')):>10}  "
                f"{_fmt_metric(summary.get('avg_mem_mib')):>11}  "
                f"{_fmt_metric(summary.get('peak_mem_mib')):>12}"
            )
        errors = tier.get("resources", {}).get("_errors") or []
        if errors:
            print(f"  {'':>10}  {'sampler':<18}  {'; '.join(errors)}")
        print(f"  {'·'*W}")
    print(f"  {'─'*W}")


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
    measure_start_s: float = 0.0
    measure_end_s: float = float("inf")
    lock:      threading.Lock = field(default_factory=threading.Lock)


def _make_on_message(stats: ClientStats):
    """Return an on_message callback that records into *stats*."""
    def _on_message(client, userdata, msg):
        now = time.monotonic()
        parts = msg.topic.split("/")
        leaf = parts[-1] if parts else msg.topic

        with stats.lock:
            if not (stats.measure_start_s <= now < stats.measure_end_s):
                return
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
    resources:     dict


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

    def _measure_window() -> float:
        start = time.monotonic()
        time.sleep(duration_s)
        return time.monotonic() - start

    elapsed, resources = _measure_with_resources(duration_s, _measure_window)

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
        resources=resources,
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
    resources:         dict


def _wait_for_first_messages(all_stats: list[ClientStats], timeout_s: float) -> None:
    """Wait until each client has received at least one message or timeout."""
    deadline = time.monotonic() + max(0.0, timeout_s)
    while time.monotonic() < deadline:
        ready = 0
        for s in all_stats:
            with s.lock:
                if s.counts:
                    ready += 1
        if ready >= len(all_stats):
            return
        time.sleep(0.05)


def _reset_client_stats(all_stats: list[ClientStats]) -> None:
    """Clear startup samples before timed measurement begins."""
    for s in all_stats:
        with s.lock:
            s.counts.clear()
            s.first_msg.clear()
            s.last_msg.clear()
            s.latencies.clear()
            s.intervals.clear()


def _set_measurement_window(
    all_stats: list[ClientStats], start_s: float, end_s: float,
) -> None:
    """Set the inclusive/exclusive receive window for each client."""
    for s in all_stats:
        with s.lock:
            s.measure_start_s = start_s
            s.measure_end_s = end_s


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

        # Ensure the first tier does not include subscription warm-up time.
        warmup_s = max(2.0, min(10.0, duration_s))
        _wait_for_first_messages(all_stats, timeout_s=warmup_s)
        _reset_client_stats(all_stats)

        def _measure_window() -> float:
            start = time.monotonic()
            end = start + duration_s
            _set_measurement_window(all_stats, start, end)
            remaining = end - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            # Stop counting immediately when the timed window ends.
            _set_measurement_window(all_stats, float("inf"), float("inf"))
            return end - start

        elapsed, resources = _measure_with_resources(duration_s, _measure_window)
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
        resources=resources,
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
            "resources": t.resources,
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
    parser.add_argument("--sweep-rates", default="20,50,100,200",
                        metavar="HZ_LIST",
                        help="Comma-separated publish rates (Hz) for the bridge "
                             "stress sweep (default: 20,50,100,200).")
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
        print("  Inter-tier gap: 2s")
        print(f"  Counts: {counts}")
        print(f"{'─'*80}")
        client_tiers: list[_ClientSweepTier] = []
        for i, n in enumerate(counts):
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
            if i < len(counts) - 1:
                time.sleep(2.0)
        if client_tiers:
            _print_client_sweep_table(client_tiers)
            report_client_scaling = _client_scaling_report_dict(client_tiers)
            _print_resource_table(
                "Client scaling resource utilization",
                report_client_scaling["tiers"],
                "Clients",
                lambda tier: str(tier["n_clients"]),
            )

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
                        "resources": r.resources,
                    }
                    for r in bridge_results
                ],
            }
            _print_resource_table(
                "Bridge sweep resource utilization",
                report_bridge["tiers"],
                "Cap (Hz)",
                lambda tier: f"{tier['hz']:.0f}",
            )
        # If user only asked for bridge sweep, exit here.
        if not args.client_sweep:
            if args.html_report:
                _emit_html(args.html_report, report_meta, report_system,
                           report_health, report_client_scaling,
                           report_bridge)
            return

    # If --client-sweep is set we skip the one-shot passive observation
    # (client-sweep already covers that at multiple N values).
    if args.client_sweep:
        if args.html_report:
            _emit_html(args.html_report, report_meta, report_system,
                       report_health, report_client_scaling,
                       report_bridge)
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

    if args.html_report:
        _emit_html(args.html_report, report_meta, report_system,
                   report_health, report_client_scaling, report_bridge)


# --------------------------------------------------------------------------
# HTML report snapshot helpers
# --------------------------------------------------------------------------

def _emit_html(path, meta, system, health, client_scaling, bridge):
    try:
        write_html_report(
            Path(path),
            meta=meta, system=system, health=health,
            client_scaling=client_scaling, bridge=bridge,
        )
        print(f"\n  HTML report written to {path}")
    except Exception as exc:
        print(f"\n  WARNING: could not write HTML report: {exc}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
