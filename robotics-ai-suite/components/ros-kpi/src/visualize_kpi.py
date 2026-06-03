#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
r"""
visualize_kpi.py — KPI chart generator for ROS 2 benchmark results.

Generates publication-ready PNG/SVG charts from kpi.json files produced
by the benchmark framework.  Designed for CI artifact embedding and
README inclusion.

Charts
------
  latency_histogram    Per-node mean / p50 / p90 latency bar chart
  sku_comparison       Cross-SKU latency bar chart (requires >= 2 --kpi files)
  resource_utilization CPU / GPU / NPU utilization breakdown
  throughput_drop      Level 2 throughput & drop-rate (requires kpi_level2.json)

Usage
-----
  # All charts for a session directory
  uv run python src/visualize_kpi.py --session <dir>

  # Explicit KPI files with labels (for cross-SKU comparison)
  uv run python src/visualize_kpi.py \
      --kpi mtl.json arl.json ptl.json \
      --label MTL ARL PTL \
      --output-dir charts/

  # Choose output format
  uv run python src/visualize_kpi.py --session <dir> --format svg

Exit codes: 0 = success, 1 = error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — safe in CI / headless environments
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt        # noqa: E402
import numpy as np                     # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

_STAGE_COLORS = {
    "Sensor":     "#3b82f6",   # blue
    "Perception": "#8b5cf6",   # purple
    "Planning":   "#f59e0b",   # amber
    "Control":    "#10b981",   # green
    "Other":      "#6b7280",   # gray
}

# Distinct colours for up to 8 SKUs in sku_comparison.
_SKU_PALETTE = [
    "#ef4444",  # red
    "#3b82f6",  # blue
    "#10b981",  # green
    "#f59e0b",  # amber
    "#8b5cf6",  # purple
    "#06b6d4",  # cyan
    "#f97316",  # orange
    "#84cc16",  # lime
]

# (key_suffix_for_ms_field, display_label, bar_alpha)
# alpha descends from p90 → mean so worst-case stands out most prominently.
_BAR_METRICS = [
    ("mean", "Mean (avg)",    0.35),
    ("p50",  "p50  (median)", 0.65),
    ("p90",  "p90  (worst)",  1.0),
]


# ──────────────────────────────────────────────────────────────────────────────
#  SKU inference
# ──────────────────────────────────────────────────────────────────────────────

# Ordered list of (regex_pattern, sku_label) pairs.
# Patterns are matched against metadata.hardware.cpu_model (case-insensitive).
# First match wins; falls back to the raw model string if nothing matches.

_SKU_PATTERNS = [
    # Panther Lake (Core Ultra 300 series, 3rd gen Core Ultra)
    (r"Ultra\s+\d+\s+3\d{2}",    "PTL"),
    # Lunar Lake (Core Ultra 200V series) — must precede ARL (both match 2\d{2})
    (r"Ultra\s+\d+\s+2\d{2}V",   "LNL"),
    # Arrow Lake (Core Ultra 200 series)
    (r"Ultra\s+\d+\s+2\d{2}",    "ARL"),
    # Meteor Lake (Core Ultra 100 series)
    (r"Ultra\s+\d+\s+1\d{2}",    "MTL"),
    # Raptor Lake Refresh (14th gen Core iX)
    (r"14th\s+Gen",               "RPL-R"),
    # Raptor Lake (13th gen Core iX)
    (r"13th\s+Gen",               "RPL"),
    # Alder Lake-N (N-series low-power: N95/N100/N200, i3-N305, i5-N200)
    # Must precede ADL to avoid the broader 12th Gen match swallowing these.
    (r"i\d-N\d{3}|\bN\d{2,3}\b", "ADL-N"),
    # Alder Lake (12th gen Core iX)
    (r"12th\s+Gen",               "ADL"),
    # Tiger Lake (11th gen)
    (r"11th\s+Gen",               "TGL"),
    # Atom / low-power
    (r"Atom",                     "Atom"),
]


def _infer_sku_label(kpi: dict) -> str:
    """
    Return a short SKU label inferred from metadata.hardware.cpu_model.

    Falls back to the raw model string (truncated) if no pattern matches,
    and to the hostname if no hardware block is present.
    """
    meta = kpi.get("metadata", {})
    hw   = meta.get("hardware", {})
    model = hw.get("cpu_model") or ""
    if model:
        for pattern, label in _SKU_PATTERNS:
            if re.search(pattern, model, re.IGNORECASE):
                return label
        # No pattern matched — extract the model number (e.g. "i7-1370P" or "Ultra 7 165U")
        m = re.search(r"i\d-\w+|Ultra\s+\d+\s+\w+", model, re.IGNORECASE)
        return m.group(0) if m else model[:20]
    # Last resort: hostname
    return meta.get("hostname", "unknown")


# ──────────────────────────────────────────────────────────────────────────────
#  Data loading
# ──────────────────────────────────────────────────────────────────────────────

def load_kpi(path: Path) -> dict:
    """Load and return a kpi.json file; raises SystemExit on error."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _representative_pair(node: str, pairs: list) -> dict:
    """Return the pair with the most samples for *node*; empty dict if none found."""
    node_pairs = [p for p in pairs if p.get("node") == node]
    if not node_pairs:
        return {}
    return max(node_pairs, key=lambda p: p.get("n", 0))


def extract_node_stats(kpi: dict) -> list:
    """
    Return one dict per node with: name, short, stage, mean_ms, p50_ms, p90_ms, hz.

    mean_ms comes from per_node; p50_ms and p90_ms come from the representative
    pair (the pair with the highest sample count for that node).  Sorted by
    mean_ms descending so the slowest node appears first.
    """
    per_node = kpi.get("per_node", {})
    pairs    = kpi.get("pairs", [])
    rows = []
    for node_name, nd in per_node.items():
        rep = _representative_pair(node_name, pairs)
        rows.append({
            "name":    node_name,
            "short":   node_name.lstrip("/").split("/")[-1],
            "stage":   nd.get("pipeline_stage", "Other"),
            "mean_ms": nd.get("mean_latency_ms"),
            "p50_ms":  rep.get("p50_ms"),
            "p90_ms":  rep.get("p90_ms"),
            "hz":      nd.get("throughput_hz"),
        })
    rows.sort(key=lambda r: r["mean_ms"] or 0, reverse=True)
    return rows


# ──────────────────────────────────────────────────────────────────────────────
#  Chart: latency_histogram
# ──────────────────────────────────────────────────────────────────────────────

def latency_histogram(kpi: dict, output_dir: Path, fmt: str = "png"):
    """
    Horizontal grouped bar chart — per-node mean / p50 / p90 latency.

    Bars are coloured by pipeline stage.  Metric opacity distinguishes
    mean (solid) from p50 (mid) from p90 (light).

    Returns the Path of the saved figure, or None if no data.
    """
    nodes = extract_node_stats(kpi)
    if not nodes:
        print("WARNING: no per_node data in KPI — skipping latency_histogram",
              file=sys.stderr)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    session  = kpi.get("metadata", {}).get("name", "session")
    n_nodes  = len(nodes)
    n_bars   = len(_BAR_METRICS)
    bar_h    = 0.22
    group_h  = n_bars * bar_h + 0.12
    fig_h    = max(4.0, n_nodes * group_h + 1.8)

    fig, ax = plt.subplots(figsize=(10, fig_h))
    y_positions = np.arange(n_nodes) * group_h

    for bar_idx, (key_suffix, label, alpha) in enumerate(_BAR_METRICS):
        x_vals = []
        colors = []
        for row in nodes:
            val = row.get(f"{key_suffix}_ms")
            x_vals.append(val if val is not None else 0.0)
            colors.append(_STAGE_COLORS.get(row["stage"], _STAGE_COLORS["Other"]))

        y_offsets = y_positions + (bar_idx - (n_bars - 1) / 2.0) * bar_h
        bars = ax.barh(y_offsets, x_vals, height=bar_h,
                       color=colors, alpha=alpha, label=label)

        # Inline value labels for bars with meaningful width
        x_max = max(x_vals) if x_vals else 1.0
        for bar, val in zip(bars, x_vals):
            if val and val > 0.02 * x_max:
                ax.text(
                    bar.get_width() + 0.3,
                    bar.get_y() + bar.get_height() / 2.0,
                    f"{val:.1f}",
                    va="center", ha="left",
                    fontsize=7, color="#374151",
                )

    # Y-axis: short node names, colour-coded by pipeline stage
    ax.set_yticks(y_positions)
    ax.set_yticklabels([r["short"] for r in nodes], fontsize=9)
    for tick, row in zip(ax.get_yticklabels(), nodes):
        tick.set_color(_STAGE_COLORS.get(row["stage"], _STAGE_COLORS["Other"]))

    ax.set_xlabel("Latency (ms)", fontsize=10)
    ax.set_title(f"Node Latency Distribution — {session}", fontsize=12, pad=12)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend: metric opacity — list from solid (p90) down to faint (mean)
    metric_handles = [
        mpatches.Patch(facecolor="#6b7280", alpha=alpha, label=lbl)
        for _, lbl, alpha in reversed(_BAR_METRICS)
    ]
    # Legend row 2: pipeline stages (only those present in the data)
    present_stages = {r["stage"] for r in nodes}
    stage_handles = [
        mpatches.Patch(facecolor=_STAGE_COLORS[stage], label=stage)
        for stage in ("Sensor", "Perception", "Planning", "Control", "Other")
        if stage in present_stages
    ]

    leg1 = ax.legend(handles=metric_handles, title="Metric",
                     loc="lower right", fontsize=8, title_fontsize=8)
    ax.add_artist(leg1)
    ax.legend(handles=stage_handles, title="Pipeline Stage",
              loc="upper right", fontsize=8, title_fontsize=8)

    plt.tight_layout()
    out_path = output_dir / f"latency_histogram.{fmt}"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  latency_histogram -> {out_path}")
    return out_path


# ──────────────────────────────────────────────────────────────────────────────
#  Chart: sku_comparison
# ──────────────────────────────────────────────────────────────────────────────

def sku_comparison(kpi_list: list, labels: list, output_dir: Path, fmt: str = "png"):
    """
    Grouped horizontal bar chart comparing mean latency per node across SKUs.

    Each SKU is a distinct colour.  A tick marker at the p90 value is overlaid
    on each bar so worst-case is visible without adding a separate bar group.
    Nodes are ordered by the first SKU's mean latency descending.  Nodes that
    only appear in some SKUs are included and shown as zero for missing ones.

    Returns the Path of the saved figure, or None if fewer than 2 KPIs supplied.
    """
    if len(kpi_list) < 2:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    stats_per_sku = [extract_node_stats(k) for k in kpi_list]

    # Build ordered node list: first SKU order, then any extras from other SKUs.
    first_means = {r["short"]: r["mean_ms"] or 0 for r in stats_per_sku[0]}
    all_shorts = list(first_means.keys())
    for sku_stats in stats_per_sku[1:]:
        for r in sku_stats:
            if r["short"] not in first_means:
                all_shorts.append(r["short"])
                first_means[r["short"]] = 0
    all_shorts.sort(key=lambda s: first_means.get(s, 0), reverse=True)

    sku_lookup = [{r["short"]: r for r in sku_stats} for sku_stats in stats_per_sku]

    n_nodes = len(all_shorts)
    n_skus  = len(kpi_list)
    bar_h   = 0.28
    gap     = 0.10
    group_h = n_skus * bar_h + gap + 0.10
    fig_h   = max(4.0, n_nodes * group_h + 2.2)

    fig, ax = plt.subplots(figsize=(11, fig_h))
    y_positions = np.arange(n_nodes) * group_h
    sku_colors  = [_SKU_PALETTE[i % len(_SKU_PALETTE)] for i in range(n_skus)]

    for sku_idx, (label, lookup, color) in enumerate(zip(labels, sku_lookup, sku_colors)):
        # Centre bars within the group.
        y_offset = y_positions + (sku_idx - (n_skus - 1) / 2.0) * bar_h

        mean_vals = []
        p90_vals  = []
        for short in all_shorts:
            row = lookup.get(short)
            mean_vals.append(row["mean_ms"] if row and row["mean_ms"] is not None else 0.0)
            p90_vals.append(row["p90_ms"]  if row and row["p90_ms"]  is not None else None)

        bars = ax.barh(y_offset, mean_vals, height=bar_h,
                       color=color, alpha=0.80, label=label)

        # p90 tick marker — solid vertical line at the p90 value.
        p90_plot  = [v if v is not None else 0.0 for v in p90_vals]
        p90_valid = [v is not None for v in p90_vals]
        ax.scatter(
            [v for v, ok in zip(p90_plot, p90_valid) if ok],
            [y for y, ok in zip(y_offset, p90_valid) if ok],
            marker="|", s=120, color=color, zorder=5, linewidths=2,
        )

        # Inline mean value labels.
        x_max = max(mean_vals) if mean_vals else 1.0
        for bar, val in zip(bars, mean_vals):
            if val and val > 0.02 * x_max:
                ax.text(
                    bar.get_width() + 0.3,
                    bar.get_y() + bar.get_height() / 2.0,
                    f"{val:.1f}",
                    va="center", ha="left",
                    fontsize=7, color="#374151",
                )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(all_shorts, fontsize=9)
    ax.set_xlabel("Latency (ms)", fontsize=10)
    title_skus = " vs ".join(labels)
    ax.set_title(f"Node Latency Comparison — {title_skus}", fontsize=12, pad=12)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend: SKU colours + metric meaning.
    sku_handles = [
        mpatches.Patch(facecolor=sku_colors[i], alpha=0.80, label=labels[i])
        for i in range(n_skus)
    ]
    metric_handles = [
        mpatches.Patch(facecolor="#6b7280", alpha=0.80, label="bar = mean (avg)"),
        plt.Line2D([0], [0], marker="|", color="#6b7280", linewidth=2,
                   markersize=10, linestyle="None", label="tick = p90 (worst)"),
    ]
    leg1 = ax.legend(handles=sku_handles, title="SKU",
                     loc="lower right", fontsize=8, title_fontsize=8)
    ax.add_artist(leg1)
    ax.legend(handles=metric_handles, title="Metric",
              loc="upper right", fontsize=8, title_fontsize=8)

    plt.tight_layout()
    out_path = output_dir / f"sku_comparison.{fmt}"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  sku_comparison   -> {out_path}")
    return out_path


# ──────────────────────────────────────────────────────────────────────────────
#  Chart: resource_utilization
# ──────────────────────────────────────────────────────────────────────────────

# Colours and safe upper bounds for each resource metric.
_RES_METRICS = [
    # (field_path, label, colour, x_max, unit)
    # CPU utilization from top-level kpi fields
    ("cpu_mean_pct",       "CPU mean %",   "#3b82f6", 100.0, "%"),
    ("cpu_max_pct",        "CPU max %",    "#1d4ed8", 100.0, "%"),
    # Temperatures from the thermal block
    ("thermal.cpu_temp_c", "CPU temp",     "#f97316", 110.0, "°C"),
    ("thermal.gpu_temp_c", "GPU temp",     "#ef4444", 105.0, "°C"),
    ("thermal.npu_temp_c", "NPU temp",     "#8b5cf6", 105.0, "°C"),
]


def _get_nested(d: dict, dotted_key: str):
    """Return d['a']['b'] for dotted_key='a.b', or None if missing."""
    keys = dotted_key.split(".")
    val = d
    for k in keys:
        if not isinstance(val, dict):
            return None
        val = val.get(k)
    return val


def resource_utilization(kpi: dict, output_dir: Path, fmt: str = "png"):
    """
    Horizontal bar chart of CPU utilization and thermal readings.

    Draws one bar per metric, coloured by resource type.  A thin vertical
    reference line marks 100 % / thermal-limit thresholds.  Metrics whose
    value is None are omitted; if all metrics are None the chart is skipped
    with a warning (common on WSL2 where /sys/class/thermal is unavailable).

    Returns the Path of the saved figure, or None if no data.
    """
    rows = []
    for field, label, color, x_max, unit in _RES_METRICS:
        val = _get_nested(kpi, field)
        if val is not None:
            rows.append({"label": label, "value": val,
                         "color": color, "x_max": x_max, "unit": unit})

    if not rows:
        print("WARNING: no resource data in KPI — skipping resource_utilization",
              file=sys.stderr)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    session = kpi.get("metadata", {}).get("name", "session")

    # Check for any throttling flags to annotate.
    throttle_flags = {
        k: _get_nested(kpi, f"thermal.{k}_throttled")
        for k in ("cpu", "gpu", "npu")
    }
    throttled = {k for k, v in throttle_flags.items() if v}

    n = len(rows)
    fig_h = max(2.5, n * 0.55 + 1.2)
    fig, ax = plt.subplots(figsize=(8, fig_h))
    y_pos = np.arange(n)

    for i, row in enumerate(rows):
        ax.barh(i, row["value"], height=0.50,
                color=row["color"], alpha=0.85)
        # Value label
        ax.text(
            row["value"] + row["x_max"] * 0.01,
            i,
            f"{row['value']:.1f}{row['unit']}",
            va="center", ha="left", fontsize=9, color="#374151",
        )
        # Reference line at the upper bound for this metric
        ax.axvline(row["x_max"], color=row["color"], linewidth=0.8,
                   linestyle="--", alpha=0.4)
        # Throttle warning marker
        resource_key = row["label"].split()[0].lower()  # "cpu", "gpu", "npu"
        if resource_key in throttled:
            ax.text(
                row["x_max"] * 1.01, i,
                "⚠ throttled", va="center", ha="left",
                fontsize=8, color="#ef4444", fontweight="bold",
            )

    ax.set_yticks(y_pos)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=9)
    ax.set_xlabel("Value", fontsize=10)
    ax.set_title(f"Resource Utilization — {session}", fontsize=12, pad=12)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Ensure x-axis has enough room for value labels
    max_x_limit = max(r["x_max"] for r in rows)
    ax.set_xlim(0, max_x_limit * 1.18)

    plt.tight_layout()
    out_path = output_dir / f"resource_utilization.{fmt}"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  resource_utilization -> {out_path}")
    return out_path


# ──────────────────────────────────────────────────────────────────────────────
#  Chart: throughput_drop
# ──────────────────────────────────────────────────────────────────────────────

def throughput_drop(kpi2: dict, output_dir: Path, fmt: str = "png"):
    """
    Horizontal grouped bar chart of pipeline end-to-end and per-stage latency
    from a kpi_level2.json file.

    Layout:
      - Top row  : full pipeline e2e latency (mean / p50 / p90).
      - One row per stage in pipeline.stage_sequence order, coloured by stage.
      - Bottleneck stage label is prefixed with ★.
      - Footer annotation shows throughput_hz and drop_rate_pct when non-null.

    Returns the Path of the saved figure, or None if kpi2 is None or contains
    no e2e_latency_ms data.
    """
    if kpi2 is None:
        return None

    e2e = kpi2.get("e2e_latency_ms", {}) or {}
    if not e2e or e2e.get("mean") is None:
        print("WARNING: no e2e_latency_ms data in kpi_level2 — skipping throughput_drop",
              file=sys.stderr)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline      = kpi2.get("pipeline", {})
    stage_seq     = pipeline.get("stage_sequence", [])
    stage_data    = kpi2.get("stage_latency_ms", {}) or {}
    bottleneck    = kpi2.get("bottleneck_stage")
    throughput_hz = kpi2.get("throughput_hz")
    drop_rate_pct = kpi2.get("drop_rate_pct")
    session       = kpi2.get("metadata", {}).get("name", "session")
    in_topic      = pipeline.get("input_topic", "")
    out_topic     = pipeline.get("output_topic", "")

    # Build rows: e2e first, then per-stage in sequence order.
    rows = []
    rows.append({
        "label":   "Pipeline (e2e)",
        "mean_ms": e2e.get("mean"),
        "p50_ms":  e2e.get("p50"),
        "p90_ms":  e2e.get("p90"),
        "stage":   "Other",   # neutral colour for the aggregate row
        "is_e2e":  True,
    })
    for stage in stage_seq:
        sd = stage_data.get(stage, {}) or {}
        label = f"★ {stage}" if stage == bottleneck else stage
        rows.append({
            "label":   label,
            "mean_ms": sd.get("mean_ms"),
            "p50_ms":  sd.get("p50_ms"),
            "p90_ms":  sd.get("p90_ms"),
            "stage":   stage,
            "is_e2e":  False,
        })
    # Also include stages that appear in stage_data but not stage_sequence.
    for stage, sd in stage_data.items():
        if stage not in stage_seq:
            label = f"★ {stage}" if stage == bottleneck else stage
            rows.append({
                "label":   label,
                "mean_ms": (sd or {}).get("mean_ms"),
                "p50_ms":  (sd or {}).get("p50_ms"),
                "p90_ms":  (sd or {}).get("p90_ms"),
                "stage":   stage,
                "is_e2e":  False,
            })

    n_rows = len(rows)
    n_bars = len(_BAR_METRICS)
    bar_h  = 0.22
    group_h = n_bars * bar_h + 0.12
    fig_h   = max(3.5, n_rows * group_h + 1.8)

    fig, ax = plt.subplots(figsize=(10, fig_h))
    y_positions = np.arange(n_rows) * group_h

    for bar_idx, (key_suffix, label, alpha) in enumerate(_BAR_METRICS):
        x_vals = []
        colors = []
        for row in rows:
            val = row.get(f"{key_suffix}_ms")
            x_vals.append(val if val is not None else 0.0)
            color = "#374151" if row["is_e2e"] else _STAGE_COLORS.get(
                row["stage"], _STAGE_COLORS["Other"])
            colors.append(color)

        y_offsets = y_positions + (bar_idx - (n_bars - 1) / 2.0) * bar_h
        bars = ax.barh(y_offsets, x_vals, height=bar_h,
                       color=colors, alpha=alpha)

        x_max = max(x_vals) if x_vals else 1.0
        for bar, val in zip(bars, x_vals):
            if val and val > 0.02 * x_max:
                ax.text(
                    bar.get_width() + 0.3,
                    bar.get_y() + bar.get_height() / 2.0,
                    f"{val:.1f}",
                    va="center", ha="left",
                    fontsize=7, color="#374151",
                )

    ax.set_yticks(y_positions)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=9)
    for tick, row in zip(ax.get_yticklabels(), rows):
        if not row["is_e2e"]:
            tick.set_color(_STAGE_COLORS.get(row["stage"], _STAGE_COLORS["Other"]))

    ax.set_xlabel("Latency (ms)", fontsize=10)
    short_in  = in_topic.split("/")[-1] if in_topic else ""
    short_out = out_topic.split("/")[-1] if out_topic else ""
    sep = f"{short_in} → {short_out}" if short_in or short_out else session
    ax.set_title(f"Pipeline Latency — {sep}", fontsize=12, pad=12)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Footer: throughput and drop rate when available.
    footer_parts = []
    if throughput_hz is not None:
        footer_parts.append(f"Throughput: {throughput_hz:.1f} Hz")
    if drop_rate_pct is not None:
        footer_parts.append(f"Drop rate: {drop_rate_pct:.1f}%")
    if footer_parts:
        ax.annotate(
            "  |  ".join(footer_parts),
            xy=(0.01, 0.01), xycoords="axes fraction",
            fontsize=8, color="#6b7280",
        )

    # Metric legend (consistent with latency_histogram).
    metric_handles = [
        mpatches.Patch(facecolor="#6b7280", alpha=alpha, label=lbl)
        for _, lbl, alpha in reversed(_BAR_METRICS)
    ]
    # Stage legend (only stages present, excluding the aggregate row).
    present_stages = {r["stage"] for r in rows if not r["is_e2e"]}
    stage_handles = [
        mpatches.Patch(facecolor=_STAGE_COLORS[stage], label=stage)
        for stage in ("Sensor", "Perception", "Planning", "Control", "Other")
        if stage in present_stages
    ]
    leg1 = ax.legend(handles=metric_handles, title="Metric",
                     loc="lower right", fontsize=8, title_fontsize=8)
    ax.add_artist(leg1)
    if stage_handles:
        ax.legend(handles=stage_handles, title="Pipeline Stage",
                  loc="upper right", fontsize=8, title_fontsize=8)

    plt.tight_layout()
    out_path = output_dir / f"throughput_drop.{fmt}"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  throughput_drop      -> {out_path}")
    return out_path


# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="visualize_kpi.py",
        description="Generate KPI charts from ROS 2 benchmark JSON results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --session monitoring_sessions/fastmapping/20260513_130427\n"
            "  %(prog)s --kpi mtl.json arl.json --label MTL ARL --output-dir charts/\n"
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--session", metavar="DIR",
        help="Session directory containing kpi.json (auto-discovers kpi_level2.json).",
    )
    src.add_argument(
        "--kpi", metavar="FILE", nargs="+",
        help="One or more kpi.json paths.  Pass multiple for cross-SKU comparison.",
    )
    p.add_argument(
        "--label", metavar="LABEL", nargs="+",
        help="SKU labels matching --kpi files (e.g. MTL ARL PTL).",
    )
    p.add_argument(
        "--kpi2", metavar="FILE",
        help="Path to kpi_level2.json for Level 2 charts (throughput / drop rate).",
    )
    p.add_argument(
        "--output-dir", metavar="DIR", default=None,
        help="Output directory for charts (default: <session>/charts or ./charts).",
    )
    p.add_argument(
        "--format", choices=["png", "svg"], default="png",
        help="Output image format (default: png).",
    )
    return p


def _resolve_inputs(args):
    """Return (kpi_list, labels, kpi2_or_None, output_dir)."""
    if args.session:
        session_dir = Path(args.session)
        kpi_path    = session_dir / "kpi.json"
        if not kpi_path.exists():
            print(f"ERROR: {kpi_path} not found", file=sys.stderr)
            sys.exit(1)
        kpi_list = [load_kpi(kpi_path)]
        labels   = [session_dir.name]
        kpi2_path = session_dir / "kpi_level2.json"
        kpi2    = load_kpi(kpi2_path) if kpi2_path.exists() else None
        out_dir = Path(args.output_dir) if args.output_dir else session_dir / "charts"
    else:
        kpi_list = [load_kpi(Path(p)) for p in args.kpi]
        labels   = args.label if args.label else [_infer_sku_label(k) for k in kpi_list]
        kpi2     = load_kpi(Path(args.kpi2)) if args.kpi2 else None
        out_dir  = Path(args.output_dir) if args.output_dir else Path("charts")

    if len(kpi_list) != len(labels):
        print("ERROR: number of --label values must match number of --kpi files",
              file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    return kpi_list, labels, kpi2, out_dir


def main() -> int:
    args = _build_parser().parse_args()
    kpi_list, labels, kpi2, out_dir = _resolve_inputs(args)

    print(f"Writing charts -> {out_dir}/")
    generated = []

    path = latency_histogram(kpi_list[0], out_dir, fmt=args.format)
    if path:
        generated.append(path)

    if len(kpi_list) > 1:
        path = sku_comparison(kpi_list, labels, out_dir, fmt=args.format)
        if path:
            generated.append(path)

    path = resource_utilization(kpi_list[0], out_dir, fmt=args.format)
    if path:
        generated.append(path)

    path = throughput_drop(kpi2, out_dir, fmt=args.format)
    if path:
        generated.append(path)

    if not generated:
        print("No charts generated.", file=sys.stderr)
        return 1

    print(f"\n{len(generated)} chart(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
