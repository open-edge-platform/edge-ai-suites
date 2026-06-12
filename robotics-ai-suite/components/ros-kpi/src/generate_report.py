#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# generate_report.py — self-contained HTML benchmark report generator
#
# Usage:
#   uv run python src/generate_report.py --session <session_dir>
#   uv run python src/generate_report.py --kpi kpi.json [--kpi2 kpi_level2.json] --output report.html
#
# Output: a single .html file with embedded CSS — no external dependencies.

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
#  Data loading
# ──────────────────────────────────────────────────────────────────────────────


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def load_session(session_dir, kpi_path=None, kpi2_path=None):
    """Return (kpi1, kpi2_or_None, session_dir_or_None)."""
    if session_dir is not None:
        d = Path(session_dir)
        kpi1 = _load_json(d / "kpi.json")
        if kpi1 is None:
            print(f"Warning: kpi.json not found in {d} — report will be partial",
                  file=sys.stderr)
        kpi2_file = d / "kpi_level2.json"
        kpi2 = _load_json(kpi2_file) if kpi2_file.exists() else None
        return kpi1, kpi2, d
    kpi1 = _load_json(kpi_path) if kpi_path else None
    kpi2 = _load_json(kpi2_path) if kpi2_path else None
    return kpi1, kpi2, None


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt(value, decimals=1, suffix=""):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:.{decimals}f}{suffix}"


def _latency_class(ms):
    """Return CSS class name based on latency threshold."""
    if ms is None:
        return "na"
    if ms < 20:
        return "good"
    if ms < 100:
        return "warn"
    return "bad"


def _pct_bar_svg(pct, max_pct=None, width=120, height=14):
    """Inline SVG progress bar."""
    if pct is None:
        return "<span class='na-text'>N/A</span>"
    cap = max_pct or 100
    fill = min(pct / cap, 1.0) * width
    color = "#22c55e" if pct < 50 else ("#f59e0b" if pct < 80 else "#ef4444")
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
        f'<rect width="{width}" height="{height}" rx="3" fill="#e5e7eb"/>'
        f'<rect width="{fill:.1f}" height="{height}" rx="3" fill="{color}"/>'
        f'</svg> <span style="font-size:0.85em">{pct:.1f}%</span>'
    )


def _throttle_badge(state):
    if state is None:
        return "<span class='badge badge-na'>N/A</span>"
    if state:
        return "<span class='badge badge-bad'>THROTTLED</span>"
    return "<span class='badge badge-good'>OK</span>"


def _temp_class(temp_c):
    if temp_c is None:
        return "na"
    if temp_c < 70:
        return "good"
    if temp_c < 90:
        return "warn"
    return "bad"


# ──────────────────────────────────────────────────────────────────────────────
#  CSS (embedded — no external URLs)
# ──────────────────────────────────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px; line-height: 1.5; color: #1f2937; background: #f9fafb;
}
.container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }

/* Header */
.report-header {
  background: linear-gradient(135deg, #0f4c81 0%, #1e78c2 100%);
  color: #fff; padding: 28px 32px; border-radius: 10px; margin-bottom: 24px;
}
.report-header h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; }
.report-header .sub { font-size: 0.9rem; opacity: 0.85; }
.hw-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px; margin-top: 16px;
}
.hw-item { background: rgba(255,255,255,0.12); border-radius: 6px; padding: 8px 12px; }
.hw-item .label { font-size: 0.75rem; opacity: 0.75; text-transform: uppercase; letter-spacing: 0.05em; }
.hw-item .value { font-weight: 600; font-size: 0.95rem; margin-top: 2px; }

/* Sections */
.section { background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
           margin-bottom: 20px; overflow: hidden; }
.section-header { padding: 14px 20px; border-bottom: 1px solid #e5e7eb;
                  font-weight: 700; font-size: 1rem; color: #111827;
                  display: flex; align-items: center; gap: 8px; }
.section-header .icon { font-size: 1.1rem; }
.section-body { padding: 16px 20px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th { background: #f3f4f6; text-align: left; padding: 8px 10px;
     font-weight: 600; color: #374151; border-bottom: 2px solid #d1d5db; }
td { padding: 7px 10px; border-bottom: 1px solid #f3f4f6; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafafa; }

/* Latency color cells */
td.good { background: #dcfce7; color: #166534; font-weight: 600; }
td.warn { background: #fef9c3; color: #854d0e; font-weight: 600; }
td.bad  { background: #fee2e2; color: #991b1b; font-weight: 600; }
td.na   { color: #9ca3af; }

/* Aggregate metric cards */
.metric-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px;
  margin-bottom: 20px;
}
.metric-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px; }
.metric-card .mc-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase;
                         letter-spacing: 0.05em; margin-bottom: 4px; }
.metric-card .mc-value { font-size: 1.4rem; font-weight: 700; color: #0f172a; }
.metric-card .mc-unit  { font-size: 0.8rem; color: #64748b; margin-top: 2px; }

/* Pipeline flow */
.pipeline-flow { display: flex; align-items: center; gap: 0; margin: 16px 0; flex-wrap: wrap; }
.stage-box {
  padding: 10px 18px; border-radius: 6px; border: 2px solid #93c5fd;
  background: #eff6ff; text-align: center; min-width: 120px;
  font-weight: 600; font-size: 0.9rem;
}
.stage-box.bottleneck { border-color: #f59e0b; background: #fffbeb; color: #92400e; }
.stage-box .stage-hz { font-size: 0.75rem; font-weight: 400; color: #6b7280; margin-top: 3px; }
.stage-box.bottleneck .stage-hz { color: #b45309; }
.stage-arrow { font-size: 1.4rem; color: #9ca3af; padding: 0 4px; line-height: 1; }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 9999px;
         font-size: 0.75rem; font-weight: 700; }
.badge-good { background: #dcfce7; color: #166534; }
.badge-warn { background: #fef9c3; color: #854d0e; }
.badge-bad  { background: #fee2e2; color: #991b1b; }
.badge-na   { background: #f3f4f6; color: #9ca3af; }
.method-badge { background: #e0f2fe; color: #075985; font-size: 0.75rem;
                padding: 2px 8px; border-radius: 4px; font-weight: 600; }

/* e2e summary row */
.e2e-row { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; }
.e2e-stat { text-align: center; }
.e2e-stat .es-val { font-size: 1.2rem; font-weight: 700; color: #0f172a; }
.e2e-stat .es-lbl { font-size: 0.72rem; color: #6b7280; text-transform: uppercase; }

/* Footer */
.report-footer { text-align: center; color: #9ca3af; font-size: 0.8rem; margin-top: 24px; }

.na-text { color: #9ca3af; font-style: italic; }
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Header section
# ──────────────────────────────────────────────────────────────────────────────


def _render_header(kpi1):
    meta = kpi1.get("metadata", {})
    hw = meta.get("hardware", {})
    name = meta.get("name", "benchmark")
    dt_raw = meta.get("datetime", "")
    try:
        dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        dt = dt_raw

    hw_items = [
        ("CPU", hw.get("cpu_model") or "N/A"),
        ("Cores", str(hw.get("cpu_cores")) if hw.get("cpu_cores") else "N/A"),
        ("RAM", f"{hw.get('total_ram_gb'):.1f} GB" if hw.get("total_ram_gb") else "N/A"),
        ("GPU", hw.get("gpu_model") or "N/A"),
        ("ROS", meta.get("ros_distro") or "N/A"),
        ("Framework", f"v{meta.get('framework_version', 'N/A')}"),
        ("Host", meta.get("hostname") or "N/A"),
        ("OS", meta.get("os") or "N/A"),
    ]
    hw_html = "".join(
        f'<div class="hw-item"><div class="label">{lbl}</div><div class="value">{val}</div></div>'
        for lbl, val in hw_items
    )
    return f"""
<div class="report-header">
  <h1>&#128202; ROS 2 Benchmark Report — {name}</h1>
  <div class="sub">{dt} &nbsp;|&nbsp; {meta.get('hostname', '')} &nbsp;|&nbsp; {meta.get('os', '')}</div>
  <div class="hw-grid">{hw_html}</div>
</div>
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Level 1 KPI section
# ──────────────────────────────────────────────────────────────────────────────


def _render_level1(kpi1):
    # Aggregate metric cards
    cards = [
        ("Throughput", _fmt(kpi1.get("throughput_hz"), 1), "Hz"),
        ("Mean Latency", _fmt(kpi1.get("mean_latency_ms"), 2), "ms"),
        ("Mean Jitter", _fmt(kpi1.get("mean_jitter_ms"), 2), "ms"),
        ("Max Jitter", _fmt(kpi1.get("max_jitter_ms"), 2), "ms"),
        ("Jitter Stdev", _fmt(kpi1.get("jitter_stdev_ms"), 2), "ms"),
        ("CPU Mean (ROS2)", _fmt(kpi1.get("cpu_mean_pct"), 1), "%"),
        ("CPU Max (ROS2)", _fmt(kpi1.get("cpu_max_pct"), 1), "%"),
    ]
    cards_html = "".join(
        f'<div class="metric-card">'
        f'<div class="mc-label">{lbl}</div>'
        f'<div class="mc-value">{val}</div>'
        f'<div class="mc-unit">{unit}</div>'
        f'</div>'
        for lbl, val, unit in cards
    )

    # Per-node table
    per_node = kpi1.get("per_node", {})
    rows = ""
    for node, nd in sorted(per_node.items()):
        lat = nd.get("mean_latency_ms")
        cls = _latency_class(lat)
        rows += (
            f"<tr>"
            f"<td>{nd.get('pipeline_stage', '')}</td>"
            f"<td><code>{node}</code></td>"
            f"<td><code>{nd.get('primary_input', '')}</code> → <code>{nd.get('primary_output', '')}</code></td>"
            f"<td>{_fmt(nd.get('throughput_hz'), 1)}</td>"
            f'<td class="{cls}">{_fmt(lat, 2)}</td>'
            f"<td>{_fmt(nd.get('mean_jitter_ms'), 2)}</td>"
            f"<td>{_fmt(nd.get('max_jitter_ms'), 2)}</td>"
            f"<td>{nd.get('num_samples', 'N/A')}</td>"
            f"</tr>"
        )

    # Pairs table
    pairs = kpi1.get("pairs", [])
    pair_rows = ""
    for p in pairs:
        lat = p.get("mean_ms")
        cls = _latency_class(lat)
        pair_rows += (
            f"<tr>"
            f"<td><code>{p.get('node', '')}</code></td>"
            f"<td><code>{p.get('input', '')}</code></td>"
            f"<td><code>{p.get('output', '')}</code></td>"
            f"<td>{p.get('n', 'N/A')}</td>"
            f'<td class="{cls}">{_fmt(lat, 2)}</td>'
            f"<td>{_fmt(p.get('p50_ms'), 2)}</td>"
            f"<td>{_fmt(p.get('p90_ms'), 2)}</td>"
            f"<td>{_fmt(p.get('max_ms'), 2)}</td>"
            f"<td>{_fmt(p.get('stdev_ms'), 2)}</td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <div class="section-header"><span class="icon">&#9654;</span> Level 1 KPI — Per-Node Latency &amp; Throughput</div>
  <div class="section-body">
    <div class="metric-grid">{cards_html}</div>

    <h3 style="margin-bottom:8px;color:#374151;font-size:0.9rem">Per-Node Summary</h3>
    <table>
      <thead>
        <tr>
          <th>Stage</th><th>Node</th><th>Input → Output</th>
          <th>Hz</th><th>Mean Lat (ms)</th><th>Mean Jitter (ms)</th>
          <th>Max Jitter (ms)</th><th>Samples</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <h3 style="margin:16px 0 8px;color:#374151;font-size:0.9rem">Trigger Pairs (raw)</h3>
    <table>
      <thead>
        <tr>
          <th>Node</th><th>Input</th><th>Output</th><th>n</th>
          <th>Mean (ms)</th><th>p50 (ms)</th><th>p90 (ms)</th><th>Max (ms)</th><th>Stdev (ms)</th>
        </tr>
      </thead>
      <tbody>{pair_rows}</tbody>
    </table>
  </div>
</div>
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Level 2 pipeline section
# ──────────────────────────────────────────────────────────────────────────────


def _render_level2(kpi2):
    if not kpi2:
        return ""

    pipeline = kpi2.get("pipeline", {})
    e2e = kpi2.get("e2e_latency_ms", {})
    stages = kpi2.get("stage_latency_ms", {})
    bottleneck = kpi2.get("bottleneck_stage", "")
    stage_seq = pipeline.get("stage_sequence", list(stages.keys()))
    method = e2e.get("method", "chained")
    drop_rate = kpi2.get("drop_rate_pct")

    # Pipeline flow diagram
    flow_parts = []
    for i, stage in enumerate(stage_seq):
        sd = stages.get(stage, {})
        hz = _fmt(sd.get("throughput_hz"), 1, " Hz") if sd else ""
        cls = "stage-box bottleneck" if stage == bottleneck else "stage-box"
        flow_parts.append(
            f'<div class="{cls}">{stage}<div class="stage-hz">{hz}</div></div>'
        )
        if i < len(stage_seq) - 1:
            flow_parts.append('<span class="stage-arrow">&#8594;</span>')
    flow_html = "".join(flow_parts)

    # E2E summary stats
    e2e_stats = [
        ("Mean", _fmt(e2e.get("mean"), 1, " ms")),
        ("p50", _fmt(e2e.get("p50"), 1, " ms")),
        ("p90", _fmt(e2e.get("p90"), 1, " ms")),
        ("p99", _fmt(e2e.get("p99"), 1, " ms")),
        ("Max", _fmt(e2e.get("max"), 1, " ms")),
        ("n", str(e2e.get("n", "N/A"))),
    ]
    e2e_html = "".join(
        f'<div class="e2e-stat"><div class="es-val">{val}</div><div class="es-lbl">{lbl}</div></div>'
        for lbl, val in e2e_stats
    )
    drop_badge = (
        f'<span class="badge badge-{"good" if (drop_rate or 0) < 1 else "warn"}">'
        f'Drop {_fmt(drop_rate, 1)}%</span>'
    ) if drop_rate is not None else ""

    # Stage table
    stage_rows = ""
    for stage in stage_seq:
        sd = stages.get(stage, {})
        if not sd:
            continue
        lat = sd.get("mean_ms")
        cls = _latency_class(lat)
        is_bn = stage == bottleneck
        bn_marker = " &#9888;" if is_bn else ""
        stage_rows += (
            f"<tr>"
            f'<td><strong>{stage}</strong>{bn_marker}</td>'
            f"<td>{_fmt(sd.get('throughput_hz'), 1)}</td>"
            f'<td class="{cls}">{_fmt(lat, 2)}</td>'
            f"<td>{_fmt(sd.get('p50_ms'), 2)}</td>"
            f"<td>{_fmt(sd.get('p90_ms'), 2)}</td>"
            f"<td>{_fmt(sd.get('max_ms'), 2)}</td>"
            f"<td>{sd.get('n', 'N/A')}</td>"
            f"<td><code>{sd.get('representative_node', '')}</code></td>"
            f"<td style='font-size:0.8em'><code>{sd.get('representative_input', '')}</code>"
            f" → <code>{sd.get('representative_output', '')}</code></td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <div class="section-header"><span class="icon">&#128279;</span> Level 2 KPI — End-to-End Pipeline Latency</div>
  <div class="section-body">
    <div class="pipeline-flow">{flow_html}</div>

    <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
      <strong>E2E Latency:</strong>
      <div class="e2e-row" style="margin:0">{e2e_html}</div>
      <span class="method-badge">{method}</span>
      {drop_badge}
    </div>

    <table>
      <thead>
        <tr>
          <th>Stage</th><th>Hz</th><th>Mean (ms)</th><th>p50 (ms)</th>
          <th>p90 (ms)</th><th>Max (ms)</th><th>n</th>
          <th>Representative Node</th><th>Topics</th>
        </tr>
      </thead>
      <tbody>{stage_rows}</tbody>
    </table>
  </div>
</div>
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Thermal / resource section
# ──────────────────────────────────────────────────────────────────────────────


def _render_thermal(kpi1):
    thermal = kpi1.get("thermal", {})
    cpu_mean = kpi1.get("cpu_mean_pct")
    cpu_max = kpi1.get("cpu_max_pct")

    temp_rows = [
        ("CPU", thermal.get("cpu_temp_c"), thermal.get("cpu_throttled")),
        ("GPU", thermal.get("gpu_temp_c"), thermal.get("gpu_throttled")),
        ("NPU", thermal.get("npu_temp_c"), thermal.get("npu_throttled")),
    ]
    t_rows_html = ""
    for label, temp, throttled in temp_rows:
        tc = _temp_class(temp)
        t_rows_html += (
            f"<tr>"
            f"<td><strong>{label}</strong></td>"
            f'<td class="{tc}">{_fmt(temp, 1, " °C") if temp is not None else "N/A"}</td>'
            f"<td>{_throttle_badge(throttled)}</td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <div class="section-header"><span class="icon">&#127777;</span> Thermal &amp; Resource Utilization</div>
  <div class="section-body">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;flex-wrap:wrap">
      <div>
        <h3 style="font-size:0.9rem;color:#374151;margin-bottom:8px">CPU Utilization (ROS2 processes)</h3>
        <table>
          <thead><tr><th>Metric</th><th>Value</th></tr></thead>
          <tbody>
            <tr><td>Mean</td><td>{_pct_bar_svg(cpu_mean)}</td></tr>
            <tr><td>Max</td><td>{_pct_bar_svg(cpu_max)}</td></tr>
          </tbody>
        </table>
      </div>
      <div>
        <h3 style="font-size:0.9rem;color:#374151;margin-bottom:8px">Thermal &amp; Throttle</h3>
        <table>
          <thead><tr><th>Component</th><th>Temp</th><th>Throttle</th></tr></thead>
          <tbody>{t_rows_html}</tbody>
        </table>
      </div>
    </div>
  </div>
</div>
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Full page assembly
# ──────────────────────────────────────────────────────────────────────────────


def render_report(kpi1, kpi2=None):
    if kpi1 is None:
        kpi1 = {}
    meta = kpi1.get("metadata", {})
    title = f"Benchmark Report — {meta.get('name', 'session')}"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fw_ver = meta.get("framework_version", "")

    header = _render_header(kpi1)
    l1 = _render_level1(kpi1)
    l2 = _render_level2(kpi2)
    thermal = _render_thermal(kpi1)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="container">
  {header}
  {l1}
  {l2}
  {thermal}
  <div class="report-footer">
    Generated {generated} &nbsp;|&nbsp; Intel Robotics Benchmark Framework v{fw_ver}
  </div>
</div>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────


def _build_parser():
    p = argparse.ArgumentParser(
        description="Generate a self-contained HTML benchmark report from KPI JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --session monitoring_sessions/fastmapping/20260513_130427\n"
            "  %(prog)s --kpi kpi.json --kpi2 kpi_level2.json --output report.html\n"
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", metavar="DIR",
                     help="Session directory containing kpi.json (and optionally kpi_level2.json)")
    src.add_argument("--kpi", metavar="FILE",
                     help="Path to kpi.json (Level 1)")
    p.add_argument("--kpi2", metavar="FILE",
                   help="Path to kpi_level2.json (Level 2, optional)")
    p.add_argument("--output", "-o", metavar="FILE",
                   help="Output HTML file (default: <session>/report.html or ./report.html)")
    return p


def main():
    args = _build_parser().parse_args()

    # Validate inputs
    if args.kpi and not Path(args.kpi).exists():
        print(f"ERROR: kpi file not found: {args.kpi}", file=sys.stderr)
        sys.exit(1)
    if args.session and not Path(args.session).exists():
        print(f"ERROR: session directory not found: {args.session}", file=sys.stderr)
        sys.exit(1)
    if args.kpi2 and not Path(args.kpi2).exists():
        print(f"ERROR: kpi2 file not found: {args.kpi2}", file=sys.stderr)
        sys.exit(1)

    kpi1, kpi2, session_dir = load_session(
        session_dir=args.session,
        kpi_path=args.kpi,
        kpi2_path=args.kpi2,
    )

    if kpi1 is None and not args.session:
        print("ERROR: --kpi file not found or not specified", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    elif session_dir:
        out_path = session_dir / "report.html"
    else:
        out_path = Path("report.html")

    html = render_report(kpi1, kpi2)
    out_path.write_text(html, encoding="utf-8")
    print(f"Report written → {out_path}")


if __name__ == "__main__":
    main()
