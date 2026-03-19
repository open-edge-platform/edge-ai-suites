#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
view_average.py — Average KPI metrics across the last N monitoring sessions.

Reads graph_timing.csv (and optionally resource_usage.log) from the N most
recent monitoring_sessions/ sub-directories and prints a consolidated summary
table showing mean ± std-dev for every metric, per topic / per process.

Usage
-----
  # average last 5 sessions (default)
  uv run python src/view_average.py

  # specify N explicitly
  uv run python src/view_average.py --runs 10

  # only timing data  /  only resource data
  uv run python src/view_average.py --timing-only
  uv run python src/view_average.py --resources-only

  # save plots
  uv run python src/view_average.py --plot --output-dir /tmp/avg_plots

  # point at a different sessions root
  uv run python src/view_average.py --sessions-dir /path/to/monitoring_sessions
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── helpers ──────────────────────────────────────────────────────────────────

def _f(v) -> Optional[float]:
    """Safe float conversion; returns None on empty / non-numeric input."""
    try:
        return float(v) if v and str(v).strip() else None
    except (ValueError, TypeError):
        return None


def _mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _std(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))


def _fmt(mean: Optional[float], std: Optional[float], unit: str = "") -> str:
    if mean is None:
        return "N/A"
    if std is not None and std > 0:
        return f"{mean:.3f} ± {std:.3f}{unit}"
    return f"{mean:.3f}{unit}"


# ── session discovery ─────────────────────────────────────────────────────────

def find_sessions(sessions_dir: Path, n: int) -> List[Path]:
    """Return the N most-recent session directories (sorted by name desc).

    Supports two layouts:
      - flat:    monitoring_sessions/<timestamp>/
      - grouped: monitoring_sessions/<algorithm>/<timestamp>/
    """
    if not sessions_dir.exists():
        return []
    # Flat layout: direct children whose names start with 8 digits.
    flat = [d for d in sessions_dir.iterdir() if d.is_dir() and d.name[:8].isdigit()]
    # Grouped layout: one level deeper inside non-timestamp subdirs.
    grouped = [
        ts
        for algo in sessions_dir.iterdir()
        if algo.is_dir() and not algo.name[:8].isdigit()
        for ts in algo.iterdir()
        if ts.is_dir() and ts.name[:8].isdigit()
    ]
    dirs = sorted(flat + grouped, key=lambda d: d.name, reverse=True)
    return dirs[:n]


# ── graph timing CSV ─────────────────────────────────────────────────────────

def parse_graph_csv(csv_path: Path) -> Dict[str, Dict[str, List[float]]]:
    """
    Return per-topic lists of numeric KPI values from one session's CSV.

    Result shape:
        { topic_name: { 'frequency_hz': [...], 'delta_time_ms': [...],
                        'latency_mean_ms': [...], 'processing_delay_ms': [...] } }
    """
    results: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    try:
        with open(csv_path, newline="") as fh:
            for row in csv.DictReader(fh):
                topic = row.get("topic_name", "").strip()
                if not topic:
                    continue
                for col in ("frequency_hz", "delta_time_ms",
                            "latency_mean_ms", "processing_delay_ms"):
                    v = _f(row.get(col))
                    if v is not None:
                        results[topic][col].append(v)
    except Exception as exc:
        print(f"  ⚠  Could not parse {csv_path}: {exc}", file=sys.stderr)
    return results


def aggregate_timing(sessions: List[Path]) -> Dict[str, Dict[str, Dict[str, Optional[float]]]]:
    """
    Merge per-session CSV data into cross-session mean ± std for each (topic, metric).

    Result shape:
        { topic: { metric: { 'mean': float|None, 'std': float|None, 'sessions': int } } }
    """
    # topic -> metric -> flat list of all values across sessions
    combined: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    session_count: Dict[str, int] = defaultdict(int)

    for sess in sessions:
        csv_path = sess / "graph_timing.csv"
        if not csv_path.exists():
            continue
        per_topic = parse_graph_csv(csv_path)
        for topic, metrics in per_topic.items():
            session_count[topic] += 1
            for metric, values in metrics.items():
                # Use the per-session mean so each session contributes one point
                m = _mean(values)
                if m is not None:
                    combined[topic][metric].append(m)

    result: Dict[str, Dict[str, Dict[str, Optional[float]]]] = {}
    for topic, metrics in combined.items():
        result[topic] = {}
        for metric, vals in metrics.items():
            result[topic][metric] = {
                "mean": _mean(vals),
                "std":  _std(vals),
                "sessions": session_count[topic],
            }
    return result


# ── resource log (pidstat) ───────────────────────────────────────────────────

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

def parse_resource_log(log_path: Path) -> Dict[str, Dict[str, List[float]]]:
    """
    Extract per-process (TGID / PID) CPU% and RSS-MB from one pidstat log.

    Result shape:
        { command: { 'cpu_pct': [...], 'rss_mb': [...] } }
    """
    results: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    try:
        with open(log_path) as fh:
            for line in fh:
                line = _ANSI.sub("", line).rstrip()
                if not re.match(r"^\d{2}:\d{2}:\d{2} [AP]M", line):
                    continue
                parts = line.split()
                if len(parts) < 12:
                    continue
                has_threads = parts[4] == "-" or (
                    parts[4].isdigit() and len(parts) >= 16
                )
                try:
                    if has_threads:
                        tid = parts[4]
                        if tid != "-":
                            continue  # only process-level rows
                        cpu_pct = float(parts[9])
                        rss_kb  = int(parts[14])
                        command = " ".join(parts[16:]) if len(parts) > 16 else parts[-1]
                    else:
                        cpu_pct = float(parts[8])
                        rss_kb  = int(parts[13])
                        command = " ".join(parts[15:]) if len(parts) > 15 else parts[-1]

                    cmd = command.strip() or "unknown"
                    results[cmd]["cpu_pct"].append(cpu_pct)
                    results[cmd]["rss_mb"].append(rss_kb / 1024.0)
                except (ValueError, IndexError):
                    continue
    except Exception as exc:
        print(f"  ⚠  Could not parse {log_path}: {exc}", file=sys.stderr)
    return results


def aggregate_resources(sessions: List[Path]) -> Dict[str, Dict[str, Dict[str, Optional[float]]]]:
    """
    Cross-session mean ± std for CPU% and RSS-MB per command.

    Result shape:
        { command: { metric: { 'mean', 'std', 'sessions' } } }
    """
    combined: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    session_count: Dict[str, int] = defaultdict(int)

    for sess in sessions:
        log_path = sess / "resource_usage.log"
        if not log_path.exists():
            continue
        per_cmd = parse_resource_log(log_path)
        for cmd, metrics in per_cmd.items():
            session_count[cmd] += 1
            for metric, values in metrics.items():
                m = _mean(values)
                if m is not None:
                    combined[cmd][metric].append(m)

    result: Dict[str, Dict[str, Dict[str, Optional[float]]]] = {}
    for cmd, metrics in combined.items():
        result[cmd] = {}
        for metric, vals in metrics.items():
            result[cmd][metric] = {
                "mean": _mean(vals),
                "std":  _std(vals),
                "sessions": session_count[cmd],
            }
    return result


# ── terminal output ───────────────────────────────────────────────────────────

def print_timing_table(
    agg: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    n_sessions: int,
) -> None:
    if not agg:
        print("  (no graph_timing.csv data found in these sessions)")
        return

    col_w = 40
    print(f"\n{'TOPIC':<{col_w}} {'Sessions':>8}  {'Freq (Hz)':>22}  {'Delta (ms)':>22}  "
          f"{'Latency mean (ms)':>24}  {'Proc delay (ms)':>24}")
    print("─" * (col_w + 8 + 22 + 22 + 24 + 24 + 10))

    for topic in sorted(agg):
        m = agg[topic]
        sessions = max(v["sessions"] for v in m.values()) if m else 0
        freq  = m.get("frequency_hz",       {})
        delta = m.get("delta_time_ms",      {})
        lat   = m.get("latency_mean_ms",    {})
        proc  = m.get("processing_delay_ms",{})

        topic_display = topic if len(topic) <= col_w else topic[: col_w - 3] + "..."
        print(
            f"{topic_display:<{col_w}} {sessions:>8}  "
            f"{_fmt(freq.get('mean'), freq.get('std')):>22}  "
            f"{_fmt(delta.get('mean'), delta.get('std')):>22}  "
            f"{_fmt(lat.get('mean'),  lat.get('std')):>24}  "
            f"{_fmt(proc.get('mean'), proc.get('std')):>24}"
        )


def print_resource_table(
    agg: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    n_sessions: int,
    top: int = 20,
) -> None:
    if not agg:
        print("  (no resource_usage.log data found in these sessions)")
        return

    # Sort by mean CPU descending
    ranked = sorted(
        agg.items(),
        key=lambda kv: kv[1].get("cpu_pct", {}).get("mean") or 0,
        reverse=True,
    )[:top]

    col_w = 50
    print(f"\n{'PROCESS':<{col_w}} {'Sessions':>8}  {'CPU %':>22}  {'RSS MB':>22}")
    print("─" * (col_w + 8 + 22 + 22 + 6))

    for cmd, metrics in ranked:
        sessions = max(v["sessions"] for v in metrics.values()) if metrics else 0
        cpu = metrics.get("cpu_pct", {})
        rss = metrics.get("rss_mb",  {})
        cmd_display = cmd if len(cmd) <= col_w else cmd[: col_w - 3] + "..."
        print(
            f"{cmd_display:<{col_w}} {sessions:>8}  "
            f"{_fmt(cpu.get('mean'), cpu.get('std')):>22}  "
            f"{_fmt(rss.get('mean'), rss.get('std')):>22}"
        )


# ── optional matplotlib plots ─────────────────────────────────────────────────

def _screen_inches() -> Tuple[float, float, float]:
    """
    Return (screen_w_in, screen_h_in, dpi).

    Tries several backends in order:
      1. tkinter  – works on most desktops
      2. Qt5/Qt6  – fallback when Tk is absent
      3. hardcoded 1920×1080 @ 96 dpi  – last resort (headless / savefig mode)
    """
    try:
        import tkinter as _tk
        root = _tk.Tk()
        root.withdraw()
        w_px = root.winfo_screenwidth()
        h_px = root.winfo_screenheight()
        # winfo_fpixels('1i') gives pixels-per-inch for the screen
        try:
            dpi = root.winfo_fpixels('1i')
        except Exception:
            dpi = 96.0
        root.destroy()
        return w_px / dpi, h_px / dpi, dpi
    except Exception:
        pass
    try:
        from PyQt5.QtWidgets import QApplication  # type: ignore
        import sys as _sys
        app = QApplication.instance() or QApplication(_sys.argv)
        screen = app.primaryScreen()
        geom   = screen.geometry()
        dpi    = screen.physicalDotsPerInch()
        return geom.width() / dpi, geom.height() / dpi, dpi
    except Exception:
        pass
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore
        import sys as _sys
        app = QApplication.instance() or QApplication(_sys.argv)
        screen = app.primaryScreen()
        geom   = screen.geometry()
        dpi    = screen.physicalDotsPerInch()
        return geom.width() / dpi, geom.height() / dpi, dpi
    except Exception:
        pass
    # Headless fallback
    return 1920 / 96, 1080 / 96, 96.0


def _latency_color(mean_ms: float) -> str:
    """Traffic-light colour based on latency magnitude."""
    if mean_ms < 10:
        return "#2ecc71"   # green  – excellent
    if mean_ms < 50:
        return "#f1c40f"   # yellow – acceptable
    if mean_ms < 200:
        return "#e67e22"   # orange – degraded
    return "#e74c3c"       # red    – poor


def plot_timing(
    agg: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    output_dir: Path,
    show: bool,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg" if not show else matplotlib.get_backend())
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available — skipping plots", file=sys.stderr)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── shared data preparation ───────────────────────────────────────────────
    topics = sorted(agg)
    lat_data, proc_data, freq_data = [], [], []
    labels = []
    for t in topics:
        lat  = agg[t].get("latency_mean_ms",     {})
        proc = agg[t].get("processing_delay_ms", {})
        freq = agg[t].get("frequency_hz",        {})
        if lat.get("mean") is not None or proc.get("mean") is not None:
            labels.append(t.lstrip("/"))
            lat_data.append( (lat.get("mean")  or 0, lat.get("std")  or 0))
            proc_data.append((proc.get("mean") or 0, proc.get("std") or 0))
            freq_data.append( freq.get("mean"))

    if not labels:
        return

    n              = len(labels)
    x              = np.arange(n)
    bar_w          = 0.38
    sw, sh, dpi    = _screen_inches()
    _, _, save_dpi = _screen_inches()
    save_dpi       = max(100, save_dpi)

    lat_means  = np.array([d[0] for d in lat_data])
    lat_stds   = np.array([d[1] for d in lat_data])
    proc_means = np.array([d[0] for d in proc_data])
    proc_stds  = np.array([d[1] for d in proc_data])
    lat_colors = [_latency_color(m) for m in lat_means]

    legend_items = [
        plt.Rectangle((0, 0), 1, 1, color="#2ecc71", alpha=0.88),
        plt.Rectangle((0, 0), 1, 1, color="#f1c40f", alpha=0.88),
        plt.Rectangle((0, 0), 1, 1, color="#e67e22", alpha=0.88),
        plt.Rectangle((0, 0), 1, 1, color="#e74c3c", alpha=0.88),
    ]
    legend_labels = ["< 10 ms  excellent", "10–50 ms  acceptable",
                     "50–200 ms  degraded", "> 200 ms  poor"]

    # ── Figure 1: Latency & Processing Delay ─────────────────────────────────
    fig_w = max(10, min(n * 0.9 + 3, sw * 0.85))
    fig_h = max(5,  min(sh * 0.75, 9))
    fig1, ax_lat = plt.subplots(figsize=(fig_w, fig_h))

    bars_lat = ax_lat.bar(x - bar_w / 2, lat_means, bar_w,
                          yerr=lat_stds, capsize=4,
                          color=lat_colors, alpha=0.88,
                          error_kw={"elinewidth": 1.2, "alpha": 0.6},
                          label="Latency mean (ms)")
    bars_proc = ax_lat.bar(x + bar_w / 2, proc_means, bar_w,
                           yerr=proc_stds, capsize=4,
                           color="tab:purple", alpha=0.72,
                           error_kw={"elinewidth": 1.2, "alpha": 0.6},
                           label="Processing delay (ms)")

    for bar in bars_lat:
        h = bar.get_height()
        if h > 0:
            ax_lat.text(bar.get_x() + bar.get_width() / 2, h * 1.02,
                        f"{h:.1f}", ha="center", va="bottom", fontsize=7, color="#333")
    for bar in bars_proc:
        h = bar.get_height()
        if h > 0:
            ax_lat.text(bar.get_x() + bar.get_width() / 2, h * 1.02,
                        f"{h:.1f}", ha="center", va="bottom", fontsize=7, color="#555")

    for threshold, label_str, colour in [
        (10,  "10 ms (good)",   "#2ecc71"),
        (50,  "50 ms (warn)",   "#f1c40f"),
        (200, "200 ms (poor)",  "#e74c3c"),
    ]:
        if threshold < max(lat_means.max(), proc_means.max()) * 1.35:
            ax_lat.axhline(threshold, color=colour, linestyle="--",
                           linewidth=0.9, alpha=0.65, label=label_str)

    ax_lat.set_xticks(x)
    ax_lat.set_xticklabels(labels, rotation=42, ha="right", fontsize=8)
    ax_lat.set_ylabel("Time (ms)", fontsize=9)
    ax_lat.set_title("Per-topic Latency & Processing Delay  (mean ± std across sessions)",
                     fontsize=10, fontweight="bold")
    ax_lat.legend(fontsize=8, ncol=3, loc="upper right")
    ax_lat.grid(axis="y", alpha=0.25)
    ax_lat.set_xlim(-0.7, n - 0.3)

    # embed colour grade legend inside the axes
    ax_lat.legend(legend_items + [plt.Line2D([0], [0], color="none")] * 0,
                  legend_labels,
                  loc="upper left", fontsize=7.5, ncol=2,
                  frameon=True, framealpha=0.85, title="Latency grades")
    # re-add the bar/threshold legend separately using handles
    handles, hlabels = ax_lat.get_legend_handles_labels()
    bar_handles  = [bars_lat, bars_proc]
    bar_labels_l = ["Latency mean (ms)", "Processing delay (ms)"]
    ax_lat.add_artist(ax_lat.legend(bar_handles, bar_labels_l,
                                    loc="upper right", fontsize=8, ncol=1))

    fig1.tight_layout()
    out1 = output_dir / "avg_latency.png"
    fig1.savefig(out1, dpi=save_dpi, bbox_inches="tight")
    print(f"  Saved: {out1}")
    if show:
        plt.show()
    plt.close(fig1)

    # ── Figure 2: Message Frequency ───────────────────────────────────────────
    freq_means_arr = np.array([f or 0 for f in freq_data])

    fig_h2 = max(4, min(sh * 0.55, 7))
    fig2, ax_freq = plt.subplots(figsize=(fig_w, fig_h2))

    freq_colors = plt.cm.Blues(0.4 + 0.5 * (freq_means_arr / (freq_means_arr.max() + 1e-9)))
    bars_f = ax_freq.bar(x, freq_means_arr, 0.6,
                         color=freq_colors, alpha=0.85)
    for bar in bars_f:
        h = bar.get_height()
        if h > 0:
            ax_freq.text(bar.get_x() + bar.get_width() / 2, h * 1.03,
                         f"{h:.1f}", ha="center", va="bottom", fontsize=7)

    ax_freq.set_xticks(x)
    ax_freq.set_xticklabels(labels, rotation=42, ha="right", fontsize=8)
    ax_freq.set_ylabel("Frequency (Hz)", fontsize=9)
    ax_freq.set_title("Message Frequency per Topic  (mean across sessions)",
                      fontsize=10, fontweight="bold")
    ax_freq.grid(axis="y", alpha=0.25)
    ax_freq.set_xlim(-0.7, n - 0.3)

    fig2.tight_layout()
    out2 = output_dir / "avg_frequency.png"
    fig2.savefig(out2, dpi=save_dpi, bbox_inches="tight")
    print(f"  Saved: {out2}")
    if show:
        plt.show()
    plt.close(fig2)


def plot_resources(
    agg: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    output_dir: Path,
    show: bool,
    top: int = 20,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg" if not show else matplotlib.get_backend())
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import numpy as np
    except ImportError:
        print("matplotlib not available — skipping plots", file=sys.stderr)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(
        agg.items(),
        key=lambda kv: kv[1].get("cpu_pct", {}).get("mean") or 0,
        reverse=True,
    )[:top]

    if not ranked:
        return

    labels     = [cmd[:45] for cmd, _ in ranked]
    cpu_means  = np.array([m.get("cpu_pct", {}).get("mean") or 0 for _, m in ranked])
    cpu_stds   = np.array([m.get("cpu_pct", {}).get("std")  or 0 for _, m in ranked])
    rss_means  = np.array([m.get("rss_mb",  {}).get("mean") or 0 for _, m in ranked])
    rss_stds   = np.array([m.get("rss_mb",  {}).get("std")  or 0 for _, m in ranked])
    n          = len(labels)
    y          = np.arange(n)

    # Colour scale: proportional to CPU %
    cpu_norm   = cpu_means / (cpu_means.max() + 1e-9)
    cpu_colors = [plt.cm.RdYlGn_r(0.15 + 0.75 * v) for v in cpu_norm]
    rss_norm   = rss_means / (rss_means.max() + 1e-9)
    rss_colors = [plt.cm.Blues(0.25 + 0.65 * v) for v in rss_norm]

    sw, sh, dpi = _screen_inches()
    fig_w = min(sw * 0.90, max(14, n * 0.3 + 8))
    fig_h = min(sh * 0.82, max(5, n * 0.45 + 2.5))
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.45)

    # ── CPU panel ─────────────────────────────────────────────────────────────
    ax_cpu = fig.add_subplot(gs[0])
    bars_c = ax_cpu.barh(y, cpu_means, xerr=cpu_stds, capsize=4,
                         color=cpu_colors, alpha=0.88,
                         error_kw={"elinewidth": 1.2, "alpha": 0.6},
                         height=0.65)
    for i, (bar, mean, std) in enumerate(zip(bars_c, cpu_means, cpu_stds)):
        if mean > 0:
            ax_cpu.text(mean + std + cpu_means.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                        f"{mean:.1f}%", va="center", fontsize=8, color="#333")

    # Reference lines
    for ref, lbl in [(100, "1 core"), (200, "2 cores"), (400, "4 cores")]:
        if ref < cpu_means.max() * 1.4:
            ax_cpu.axvline(ref, color="grey", linestyle=":", linewidth=0.9, alpha=0.7)
            ax_cpu.text(ref, n - 0.3, lbl, fontsize=7, color="grey", ha="center")

    ax_cpu.set_yticks(y)
    ax_cpu.set_yticklabels(labels, fontsize=8)
    ax_cpu.invert_yaxis()
    ax_cpu.set_xlabel("CPU  %", fontsize=9)
    ax_cpu.set_title("Average CPU Usage\n(mean ± std, ranked by CPU)",
                     fontsize=10, fontweight="bold")
    ax_cpu.grid(axis="x", alpha=0.25)

    # ── Memory panel ──────────────────────────────────────────────────────────
    ax_rss = fig.add_subplot(gs[1])
    bars_r = ax_rss.barh(y, rss_means, xerr=rss_stds, capsize=4,
                         color=rss_colors, alpha=0.88,
                         error_kw={"elinewidth": 1.2, "alpha": 0.6},
                         height=0.65)
    for i, (bar, mean, std) in enumerate(zip(bars_r, rss_means, rss_stds)):
        if mean > 0:
            ax_rss.text(mean + std + rss_means.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                        f"{mean:.0f} MB", va="center", fontsize=8, color="#333")

    # Memory reference lines
    for ref, lbl in [(256, "256 MB"), (512, "512 MB"), (1024, "1 GB")]:
        if ref < rss_means.max() * 1.4:
            ax_rss.axvline(ref, color="grey", linestyle=":", linewidth=0.9, alpha=0.7)
            ax_rss.text(ref, n - 0.3, lbl, fontsize=7, color="grey", ha="center")

    ax_rss.set_yticks(y)
    ax_rss.set_yticklabels(labels, fontsize=8)
    ax_rss.invert_yaxis()
    ax_rss.set_xlabel("RSS  MB", fontsize=9)
    ax_rss.set_title("Average Memory (RSS)\n(mean ± std)",
                     fontsize=10, fontweight="bold")
    ax_rss.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Resource Usage Summary — top {top} processes",
                 fontsize=11, fontweight="bold", y=0.98)
    fig.subplots_adjust(top=0.92)

    out_png = output_dir / "avg_resources.png"
    _, _, dpi = _screen_inches()
    fig.savefig(out_png, dpi=max(100, dpi), bbox_inches="tight")
    print(f"  Saved: {out_png}")
    if show:
        plt.show()
    plt.close(fig)


# ── table export (CSV + JSON) ────────────────────────────────────────────────

def save_timing_tables(
    agg: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    output_dir: Path,
    n_sessions: int,
) -> None:
    """Write avg_timing.csv and avg_timing.json to *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── CSV ──────────────────────────────────────────────────────────────────
    csv_path = output_dir / "avg_timing.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "topic", "sessions",
            "freq_mean_hz", "freq_std_hz",
            "delta_mean_ms", "delta_std_ms",
            "latency_mean_ms", "latency_std_ms",
            "proc_delay_mean_ms", "proc_delay_std_ms",
        ])
        for topic in sorted(agg):
            m = agg[topic]
            sessions = max(v["sessions"] for v in m.values()) if m else 0
            freq  = m.get("frequency_hz",        {})
            delta = m.get("delta_time_ms",       {})
            lat   = m.get("latency_mean_ms",     {})
            proc  = m.get("processing_delay_ms", {})
            writer.writerow([
                topic, sessions,
                freq.get("mean"),  freq.get("std"),
                delta.get("mean"), delta.get("std"),
                lat.get("mean"),   lat.get("std"),
                proc.get("mean"),  proc.get("std"),
            ])
    print(f"  Saved: {csv_path}")

    # ── JSON ─────────────────────────────────────────────────────────────────
    json_path = output_dir / "avg_timing.json"
    payload: Dict = {
        "n_sessions": n_sessions,
        "topics": {
            topic: {
                metric: {k: v for k, v in stats.items()}
                for metric, stats in metrics.items()
            }
            for topic, metrics in agg.items()
        },
    }
    with open(json_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"  Saved: {json_path}")


def save_resource_tables(
    agg: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    output_dir: Path,
    n_sessions: int,
) -> None:
    """Write avg_resources.csv and avg_resources.json to *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(
        agg.items(),
        key=lambda kv: kv[1].get("cpu_pct", {}).get("mean") or 0,
        reverse=True,
    )

    # ── CSV ──────────────────────────────────────────────────────────────────
    csv_path = output_dir / "avg_resources.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "process", "sessions",
            "cpu_mean_pct", "cpu_std_pct",
            "rss_mean_mb", "rss_std_mb",
        ])
        for cmd, metrics in ranked:
            sessions = max(v["sessions"] for v in metrics.values()) if metrics else 0
            cpu = metrics.get("cpu_pct", {})
            rss = metrics.get("rss_mb",  {})
            writer.writerow([
                cmd, sessions,
                cpu.get("mean"), cpu.get("std"),
                rss.get("mean"), rss.get("std"),
            ])
    print(f"  Saved: {csv_path}")

    # ── JSON ─────────────────────────────────────────────────────────────────
    json_path = output_dir / "avg_resources.json"
    payload = {
        "n_sessions": n_sessions,
        "processes": {
            cmd: {
                metric: {k: v for k, v in stats.items()}
                for metric, stats in metrics.items()
            }
            for cmd, metrics in agg.items()
        },
    }
    with open(json_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"  Saved: {json_path}")


def save_gpu_tables(
    gpu_agg: Dict[str, Dict[str, Optional[float]]],
    output_dir: Path,
) -> None:
    """Write avg_gpu.csv and avg_gpu.json to *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── CSV ──────────────────────────────────────────────────────────────────
    csv_path = output_dir / "avg_gpu.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "mean", "std", "sessions"])
        for key, info in gpu_agg.items():
            writer.writerow([
                key,
                info.get("mean"),
                info.get("std"),
                info.get("sessions"),
            ])
    print(f"  Saved: {csv_path}")

    # ── JSON ─────────────────────────────────────────────────────────────────
    json_path = output_dir / "avg_gpu.json"
    with open(json_path, "w") as fh:
        json.dump(gpu_agg, fh, indent=2)
    print(f"  Saved: {json_path}")


# ── main ──────────────────────────────────────────────────────────────────────

# ── GPU log (sysfs) ──────────────────────────────────────────────────────────

def aggregate_gpu(sessions: List[Path]) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
    """Average GPU busy%, act_freq, and throttle_fraction across sessions."""
    busy_pcts: List[float] = []
    act_freqs: List[float] = []
    throttle_fracs: List[float] = []

    for sess in sessions:
        log_path = sess / "gpu_usage.log"
        if not log_path.exists():
            continue
        records = []
        try:
            with open(log_path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            continue
        if not records:
            continue
        busy_pcts.append(sum(r.get('busy_pct', 0.0) for r in records) / len(records))
        act_freqs.append(sum(r.get('act_freq_mhz', 0) for r in records) / len(records))
        throttle_fracs.append(sum(1 for r in records if r.get('throttled', False)) / len(records) * 100)

    if not busy_pcts:
        return None
    return {
        'busy_pct': {'mean': _mean(busy_pcts), 'std': _std(busy_pcts), 'sessions': len(busy_pcts)},
        'act_freq_mhz': {'mean': _mean(act_freqs), 'std': _std(act_freqs), 'sessions': len(act_freqs)},
        'throttle_pct': {'mean': _mean(throttle_fracs), 'std': _std(throttle_fracs), 'sessions': len(throttle_fracs)},
    }


def plot_gpu_average(
    gpu_agg: Dict[str, Dict[str, Optional[float]]],
    output_dir: Path,
    show: bool = False,
) -> None:
    """Bar chart of average GPU busy%, frequency, and throttle fraction."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    metrics = [
        ('busy_pct', 'GPU Busy %', 'steelblue', (0, 100)),
        ('act_freq_mhz', 'Actual Freq (MHz)', 'darkorange', None),
        ('throttle_pct', 'Throttle Time %', 'firebrick', (0, 100)),
    ]
    n_sess = None
    for ax, (key, label, color, ylim) in zip(axes, metrics):
        info = gpu_agg.get(key)
        if info is None:
            ax.set_visible(False)
            continue
        mean_val = info['mean'] or 0.0
        std_val = info['std'] or 0.0
        n_sess = info.get('sessions', 0)
        ax.bar([label], [mean_val], yerr=[std_val], capsize=6,
               color=color, alpha=0.75, width=0.5)
        ax.set_title(label, fontsize=10, fontweight='bold')
        ax.set_ylabel('Value', fontsize=9)
        if ylim:
            ax.set_ylim(*ylim)
        ax.grid(axis='y', alpha=0.3)

    n_label = f" ({n_sess} session(s))" if n_sess else ""
    fig.suptitle(f"Intel GPU Average{n_label}", fontsize=12, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.88)
    plt.tight_layout()

    out_png = output_dir / "avg_gpu.png"
    fig.savefig(out_png, dpi=150, bbox_inches='tight')
    print(f"  Saved: {out_png}")
    if show:
        plt.show()
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Average KPI metrics across the last N monitoring sessions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--runs", "-n",
        type=int, default=5,
        metavar="N",
        help="Number of most-recent sessions to average (default: 5)",
    )
    parser.add_argument(
        "--sessions-dir",
        default="monitoring_sessions",
        metavar="DIR",
        help="Root directory of monitoring sessions (default: monitoring_sessions)",
    )
    parser.add_argument(
        "--timing-only", action="store_true",
        help="Only show graph timing averages (skip resource log)",
    )
    parser.add_argument(
        "--resources-only", action="store_true",
        help="Only show resource averages (skip graph timing CSV)",
    )
    parser.add_argument(
        "--plot", action="store_true",
        help="Generate bar-chart PNG summaries",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Open plot windows interactively (implies --plot)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        metavar="DIR",
        help="Directory to save plots (default: monitoring_sessions/average_N/)",
    )
    parser.add_argument(
        "--top", type=int, default=20,
        metavar="K",
        help="Show top-K processes in resource table (default: 20)",
    )
    parser.add_argument(
        "--save-tables", action="store_true",
        help="Save average tables as CSV and JSON (auto-enabled with --plot)",
    )
    args = parser.parse_args()

    if args.show:
        args.plot = True
    if args.plot:
        args.save_tables = True

    sessions_dir = Path(args.sessions_dir)
    sessions = find_sessions(sessions_dir, args.runs)

    if not sessions:
        print(f"No monitoring sessions found in '{sessions_dir}'. "
              "Run 'make monitor' first.")
        sys.exit(1)

    n_found = len(sessions)
    print("╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  ROS2 KPI — Average across last {args.runs} session(s)               ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"\nUsing {n_found} session(s) (of {args.runs} requested):")
    for s in reversed(sessions):   # oldest first
        print(f"  • {s.name}")
    print()

    output_dir = Path(args.output_dir) if args.output_dir else (
        sessions_dir / f"average_{args.runs}"
    )

    # ── timing ---------------------------------------------------------------
    if not args.resources_only:
        print("══════════════════════════════════════════")
        print(f" GRAPH TIMING  (avg of {n_found} session(s))")
        print("══════════════════════════════════════════")
        timing_agg = aggregate_timing(sessions)
        print_timing_table(timing_agg, n_found)
        if timing_agg:
            if args.save_tables:
                print("\nSaving timing tables...")
                save_timing_tables(timing_agg, output_dir, n_found)
            if args.plot:
                print("\nSaving timing plots...")
                plot_timing(timing_agg, output_dir, args.show)

    print()

    # ── resources ------------------------------------------------------------
    if not args.timing_only:
        print("══════════════════════════════════════════")
        print(f" RESOURCE USAGE  (avg of {n_found} session(s))")
        print("══════════════════════════════════════════")
        resource_agg = aggregate_resources(sessions)
        print_resource_table(resource_agg, n_found, top=args.top)
        if resource_agg:
            if args.save_tables:
                print("\nSaving resource tables...")
                save_resource_tables(resource_agg, output_dir, n_found)
            if args.plot:
                print("\nSaving resource plots...")
                plot_resources(resource_agg, output_dir, args.show, top=args.top)

        # GPU average
        gpu_agg = aggregate_gpu(sessions)
        if gpu_agg:
            print("\n── GPU Average ──")
            for key, info in gpu_agg.items():
                print(f"  {key:20s}: {info['mean']:.1f} ± {info['std']:.1f}  (n={info['sessions']})")
            if args.save_tables:
                print("\nSaving GPU tables...")
                save_gpu_tables(gpu_agg, output_dir)
            if args.plot:
                print("\nSaving GPU average plot...")
                plot_gpu_average(gpu_agg, output_dir, args.show)

    print()
    if args.plot or args.save_tables:
        print(f"Output saved to: {output_dir}/")


if __name__ == "__main__":
    main()
