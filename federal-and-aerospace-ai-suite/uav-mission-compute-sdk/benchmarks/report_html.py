# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
HTML report generator for the MAVLink→MQTT benchmark.

Layout (top-down):
  1. Header cards — run metadata, host system specs, deployment-component
     health (broker, bridge, container states).
  2. Two focused plots — one per benchmark mode:
       a) Client scaling  — per-client mean rate vs. number of subscribers
       b) Bridge sweep    — observed Hz per topic vs. requested cap
  3. Raw data tables under each plot.

Chart.js is loaded from a CDN; open the resulting file with network access.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


_CHARTJS_CDN = (
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def write_html_report(
    path: Path,
    *,
    meta:   dict[str, Any],
    system: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    client_scaling: dict[str, Any] | None = None,
    bridge: dict[str, Any] | None = None,
) -> None:
    """Write a self-contained HTML report to *path*.

    Any of the result dicts may be ``None``; sections without data are omitted.
    """
    sections: list[str] = []
    if client_scaling:
        sections.append(_render_client_scaling(client_scaling))
    if bridge:
        sections.append(_render_bridge(bridge))
    body = "\n".join(sections) if sections else (
        '<section><p><em>No benchmark modes produced results.</em></p></section>'
    )

    doc = _HTML_TEMPLATE.format(
        css=_CSS,
        chart_cdn=html.escape(_CHARTJS_CDN),
        header=_render_header(meta, system, health),
        sections=body,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------
# Header (metadata + system + health)
# --------------------------------------------------------------------------

def _render_header(meta: dict, system: dict | None, health: dict | None) -> str:
    meta   = meta or {}
    system = system or {}
    health = health or {}

    meta_card = _card("Run", [
        ("Generated", meta.get("generated_at", "")),
        ("Broker",    f"{meta.get('host', '')}:{meta.get('port', '')}"),
        ("UAV ID",    meta.get("uav_id", "")),
    ])

    system_card = _card("System", [
        ("Host",   system.get("hostname")),
        ("OS",     system.get("system")),
        ("Arch",   system.get("machine")),
        ("CPU",    system.get("cpu_model")),
        ("Cores",  system.get("cpu_count")),
        ("Memory", f"{system.get('mem_gb')} GB" if system.get("mem_gb") else None),
    ]) if system else ""

    health_card = _render_health_card(health) if health else ""

    return (
        f'<h1>MAVLink → MQTT Benchmark Report</h1>'
        f'<div class="cards">{meta_card}{system_card}{health_card}</div>'
    )


def _render_health_card(health: dict) -> str:
    rows: list[tuple[str, str]] = []
    broker_state = health.get("broker", "unknown")
    rows.append(("MQTT broker",
                 _status_badge(broker_state == "ok", broker_state or "unknown")))

    tel_active = bool(health.get("telemetry_active"))
    tel_label  = "streaming" if tel_active else "no messages"
    rows.append(("Bridge telemetry",
                 _status_badge(tel_active, tel_label)))

    containers = health.get("containers") or []
    for c in containers:
        state_ok = str(c.get("state", "")).lower() in ("running", "up")
        rows.append((
            c.get("name", "?"),
            _status_badge(state_ok, c.get("status") or c.get("state") or "?"),
        ))
    return _card("Deployment health", rows, allow_html=True)


def _card(title: str, rows: list[tuple[str, Any]], *, allow_html: bool = False) -> str:
    items = []
    for k, v in rows:
        if v in (None, ""):
            continue
        value_html = v if allow_html else html.escape(str(v))
        items.append(
            f'<div class="row"><span>{html.escape(k)}</span>'
            f'<code>{value_html}</code></div>'
        )
    return (
        f'<div class="card">'
        f'<h3>{html.escape(title)}</h3>{"".join(items)}'
        f'</div>'
    )


def _status_badge(ok: bool, text: str) -> str:
    cls = "ok" if ok else "bad"
    return f'<span class="badge {cls}">{html.escape(str(text))}</span>'


# --------------------------------------------------------------------------
# Section renderers (one plot each; metric selectable via <select>)
# --------------------------------------------------------------------------

# Palette used both for topic series (bridge sweep) and single-series charts.
_PALETTE = [
    ("rgba(66, 133, 244, 1)",  "rgba(66, 133, 244, 0.15)"),
    ("rgba(234, 67, 53, 1)",   "rgba(234, 67, 53, 0.15)"),
    ("rgba(52, 168, 83, 1)",   "rgba(52, 168, 83, 0.15)"),
    ("rgba(251, 188, 5, 1)",   "rgba(251, 188, 5, 0.15)"),
    ("rgba(103, 58, 183, 1)",  "rgba(103, 58, 183, 0.15)"),
    ("rgba(0, 172, 193, 1)",   "rgba(0, 172, 193, 0.15)"),
]


def _render_client_scaling(cs: dict) -> str:
    tiers = cs.get("tiers", [])
    if not tiers:
        return ""

    # Raw data as list of records — the JS switcher slices columns from this.
    records = [{
        "n_clients": t["n_clients"],
        "mean_rate": round(t.get("mean_rate", 0.0), 2),
        "agg_rate":  round(t.get("agg_rate", 0.0),  2),
        "cv":        round(t.get("cv", 0.0), 2),
        "avg_lat":   _ms(t.get("avg_lat")),
        "p99_lat":   _ms(t.get("p99_lat")),
    } for t in tiers]

    metrics = {
        "mean_rate": {"label": "Per-client mean rate",  "unit": "Hz"},
        "agg_rate":  {"label": "Aggregate rate",         "unit": "Hz"},
        "cv":        {"label": "Rate CV",                "unit": "%"},
        "avg_lat":   {"label": "Avg latency",            "unit": "ms"},
        "p99_lat":   {"label": "P99 latency",            "unit": "ms"},
    }

    chart_html = _switchable_chart(
        chart_id="chart-client-scaling",
        title="Metric vs. subscriber count",
        x_label="Subscribers (N)",
        x_field="n_clients",
        records=records,
        metrics=metrics,
        default_metric="mean_rate",
    )

    rows = "".join(
        f"<tr><td>{r['n_clients']}</td>"
        f"<td>{r['mean_rate']:.2f}</td>"
        f"<td>{r['agg_rate']:.2f}</td>"
        f"<td>{r['cv']:.2f}</td>"
        f"<td>{_fmt(r['avg_lat'])}</td>"
        f"<td>{_fmt(r['p99_lat'])}</td></tr>"
        for r in records
    )
    table = (
        '<table class="tbl"><thead><tr>'
        '<th>Clients</th><th>Per-client mean (Hz)</th>'
        '<th>Aggregate (Hz)</th><th>CV (%)</th>'
        '<th>Avg lat (ms)</th><th>P99 lat (ms)</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table>'
    )

    return (
        f'<section id="client-scaling">'
        f'<h2>Client scaling</h2>'
        f'<p>Passive observation at escalating subscriber counts · '
        f'duration per tier: <code>{cs.get("duration_s", 0):.1f}s</code></p>'
        f'{_pipeline_coverage("client-scaling")}'
        f'{chart_html}{table}{_render_resource_utilization(cs, chart_prefix="client-scaling", x_label="Subscribers (N)", x_field="n_clients")}'
        f'</section>'
    )


def _render_bridge(b: dict) -> str:
    tiers = b.get("tiers", [])
    if not tiers:
        return ""

    caps   = [t["hz"] for t in tiers]
    topics = _bridge_topics(tiers)

    # Series-per-topic data.  Values are per topic per metric.
    values: dict[str, dict[str, list]] = {}
    for topic in topics:
        obs, alat, plat, ach = [], [], [], []
        for t in tiers:
            v = t["topics"].get(topic, {})
            obs.append(_num(v.get("obs_hz")))
            alat.append(_num(v.get("avg_lat")))
            plat.append(_num(v.get("p99_lat")))
            ach.append(_num(v.get("achieved_pct")))
        values[topic] = {"obs_hz": obs, "avg_lat": alat,
                         "p99_lat": plat, "achieved_pct": ach}

    metrics = {
        "obs_hz":       {"label": "Observed Hz",  "unit": "Hz",
                         "show_yeqx": True},
        "achieved_pct": {"label": "Achieved % of cap", "unit": "%",
                         "show_yeqx": False},
        "avg_lat":      {"label": "Avg latency",  "unit": "ms",
                         "show_yeqx": False},
        "p99_lat":      {"label": "P99 latency",  "unit": "ms",
                         "show_yeqx": False},
    }

    palette_js = [{"border": b, "bg": g} for b, g in _PALETTE]
    data_js = json.dumps({
        "caps": caps, "topics": topics, "values": values,
        "palette": palette_js, "metrics": metrics,
    }, default=_json_default)

    chart_id = "chart-bridge"
    select_options = "".join(
        f'<option value="{html.escape(k)}"'
        f'{" selected" if k == "obs_hz" else ""}>'
        f'{html.escape(v["label"])} ({v["unit"]})</option>'
        for k, v in metrics.items()
    )
    chart_html = (
        f'<div class="chart-box">'
        f'<div class="chart-head">'
        f'<label for="{chart_id}-metric">Metric:</label> '
        f'<select id="{chart_id}-metric">{select_options}</select>'
        f'</div>'
        f'<div class="canvas-wrap"><canvas id="{chart_id}"></canvas></div>'
        f'<script>(function(){{'
        f'const D = {data_js};'
        f'const el = document.getElementById("{chart_id}");'
        f'const sel = document.getElementById("{chart_id}-metric");'
        f'function build(metric) {{'
        f'  const spec = D.metrics[metric];'
        f'  const ds = D.topics.map((t, i) => {{'
        f'    const p = D.palette[i % D.palette.length];'
        f'    return {{label: t, data: D.values[t][metric],'
        f'      borderColor: p.border, backgroundColor: p.bg,'
        f'      fill: false, tension: 0.15, spanGaps: true}};'
        f'  }});'
        f'  if (spec.show_yeqx) {{'
        f'    ds.push({{label: "y = x (cap)", data: D.caps,'
        f'      borderColor: "rgba(120, 120, 120, 0.7)",'
        f'      borderDash: [4, 4], fill: false, pointRadius: 0}});'
        f'  }}'
        f'  return {{'
        f'    type: "line",'
        f'    data: {{labels: D.caps, datasets: ds}},'
        f'    options: {{responsive: true, maintainAspectRatio: false,'
        f'      plugins: {{legend: {{position: "bottom",'
        f'                            labels: {{boxWidth: 12}}}}}},'
        f'      scales: {{'
        f'        x: {{title: {{display: true, text: "Cap (Hz)"}}}},'
        f'        y: {{beginAtZero: true,'
        f'              title: {{display: true, text: spec.unit}}}}'
        f'      }}'
        f'    }}'
        f'  }};'
        f'}}'
        f'let chart = new Chart(el, build(sel.value));'
        f'sel.addEventListener("change", () => {{'
        f'  chart.destroy(); chart = new Chart(el, build(sel.value));'
        f'}});'
        f'}})();</script>'
        f'</div>'
    )

    rows = []
    for t in tiers:
        for topic in topics:
            v = t["topics"].get(topic)
            if v is None:
                continue
            ach = v.get("achieved_pct")
            ach_str = "—" if ach is None else f"{ach:.1f}%"
            rows.append(
                f"<tr><td>{t['hz']:.0f}</td>"
                f"<td>{html.escape(topic)}</td>"
                f"<td>{v['count']}</td>"
                f"<td>{v['obs_hz']:.2f}</td>"
                f"<td>{ach_str}</td>"
                f"<td>{_fmt(v.get('avg_lat'))}</td>"
                f"<td>{_fmt(v.get('p99_lat'))}</td></tr>"
            )
    table = (
        '<table class="tbl left-2"><thead><tr>'
        '<th>Cap (Hz)</th><th>Topic</th><th>Msgs</th><th>Obs (Hz)</th>'
        '<th>Achieved</th><th>Avg lat (ms)</th><th>P99 lat (ms)</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    )

    return (
        f'<section id="bridge">'
        f'<h2>Bridge stress sweep</h2>'
        f'<p>Recreates <code>companion-bridge</code> at each cap tier · '
        f'duration per tier: <code>{b.get("duration_s", 0):.1f}s</code> · '
        f'latency = recv − reader_ts_ns (full path)</p>'
        f'{_pipeline_coverage("bridge")}'
        f'{chart_html}{table}{_render_resource_utilization(b, chart_prefix="bridge", x_label="Cap (Hz)", x_field="hz")}'
        f'</section>'
    )


def _render_resource_utilization(section: dict, *, chart_prefix: str, x_label: str, x_field: str) -> str:
    tiers = section.get("tiers", [])
    if not tiers:
        return ""

    containers = []
    for tier in tiers:
        for name in (tier.get("resources") or {}):
            if name.startswith("_") or name in containers:
                continue
            containers.append(name)
    if not containers:
        return ""

    x_values = [tier.get(x_field) for tier in tiers]
    metrics = {
        "avg_cpu_pct": {
            "label": "CPU average",
            "unit": "CPU %",
            "series": {
                name: [_num((tier.get("resources") or {}).get(name, {}).get("avg_cpu_pct"))
                       for tier in tiers]
                for name in containers
            },
        },
        "avg_mem_mib": {
            "label": "Memory average",
            "unit": "Mem (MiB)",
            "series": {
                name: [_num((tier.get("resources") or {}).get(name, {}).get("avg_mem_mib"))
                       for tier in tiers]
                for name in containers
            },
        },
    }

    rows = []
    for tier in tiers:
        x_value = tier.get(x_field)
        row = [f"<tr><td>{html.escape(str(x_value))}</td>"]
        for name in containers:
            summary = (tier.get("resources") or {}).get(name, {})
            row.append(f"<td>{_fmt(summary.get('avg_cpu_pct'))}</td>")
            row.append(f"<td>{_fmt(summary.get('avg_mem_mib'))}</td>")
        row.append("</tr>")
        rows.append("".join(row))

    header_groups = "".join(
        f'<th colspan="2">{html.escape(name)}</th>'
        for name in containers
    )
    header_metrics = "".join(
        '<th>CPU %</th><th>Mem (MiB)</th>'
        for _name in containers
    )

    return (
        '<div class="resource-block">'
        '<h3>Container resource utilization</h3>'
        '<p>Average CPU and average memory usage captured from Docker stats over each measurement window.</p>'
        f'{_pipeline_coverage("resources")}'
        f'{_resource_metric_chart(chart_id=f"{chart_prefix}-resources", title="Container utilization", x_values=x_values, x_label=x_label, metrics=metrics)}'
        '<table class="tbl resource-tbl"><thead>'
        f'<tr><th rowspan="2">{html.escape(x_label)}</th>{header_groups}</tr>'
        f'<tr>{header_metrics}</tr>'
        '</thead><tbody>' + "".join(rows) + '</tbody></table>'
        '</div>'
    )


def _pipeline_coverage(kind: str) -> str:
    """Render plain pipeline coverage text for each result type."""
    if kind == "client-scaling":
        pipeline = (
            'PX4 emit → MAVSDK read → companion-bridge publish → '
            '<strong>MQTT broker → subscriber receive</strong>'
        )
    elif kind == "bridge":
        pipeline = (
            '<strong>PX4 emit → MAVSDK read → companion-bridge publish → '
            'MQTT broker → subscriber receive</strong>'
        )
    else:
        return ""

    return f'<p>{pipeline}</p>'


def _resource_metric_chart(
    *,
    chart_id: str,
    title: str,
    x_values: list,
    x_label: str,
    metrics: dict[str, dict],
) -> str:
    data_js = json.dumps({
        "x": x_values,
        "metrics": metrics,
        "palette": [{"border": b, "bg": g} for b, g in _PALETTE],
        "x_label": x_label,
    }, default=_json_default)
    select_options = "".join(
        f'<option value="{html.escape(key)}">'
        f'{html.escape(spec["label"])} ({html.escape(spec["unit"])})</option>'
        for key, spec in metrics.items()
    )
    return (
        f'<div class="chart-box">'
        f'<div class="chart-head">'
        f'<h4>{html.escape(title)}</h4>'
        f'<label for="{chart_id}-metric">Metric:</label> '
        f'<select id="{chart_id}-metric">{select_options}</select>'
        f'</div>'
        f'<div class="canvas-wrap"><canvas id="{chart_id}"></canvas></div>'
        f'<script>(function(){{'
        f'const D = {data_js};'
        f'const el = document.getElementById("{chart_id}");'
        f'const sel = document.getElementById("{chart_id}-metric");'
        f'function build(metric) {{'
        f'  const spec = D.metrics[metric];'
        f'  const datasets = Object.entries(spec.series).map(([label, data], i) => {{'
        f'    const p = D.palette[i % D.palette.length];'
        f'    return {{label, data, borderColor: p.border, backgroundColor: p.bg, fill: false, tension: 0.15, spanGaps: true}};'
        f'  }});'
        f'  return {{type: "line", data: {{labels: D.x, datasets}}, options: {{responsive: true, maintainAspectRatio: false, plugins: {{legend: {{position: "bottom", labels: {{boxWidth: 12}}}}}}, scales: {{x: {{title: {{display: true, text: D.x_label}}}}, y: {{beginAtZero: true, title: {{display: true, text: spec.unit}}}}}} }} }};'
        f'}}'
        f'let chart = new Chart(el, build(sel.value));'
        f'sel.addEventListener("change", () => {{'
        f'  chart.destroy(); chart = new Chart(el, build(sel.value));'
        f'}});'
        f'}})();</script>'
        f'</div>'
    )


# --------------------------------------------------------------------------
# Single-series switchable chart (used by client scaling)
# --------------------------------------------------------------------------

def _switchable_chart(
    *,
    chart_id: str,
    title: str,
    x_label: str,
    x_field: str,
    records: list[dict],
    metrics: dict[str, dict],
    default_metric: str,
) -> str:
    """Render a chart-box with a metric <select> above a single-series line."""
    data_js = json.dumps({
        "x": [r[x_field] for r in records],
        "records": records,
        "metrics": metrics,
    }, default=_json_default)

    select_options = "".join(
        f'<option value="{html.escape(k)}"'
        f'{" selected" if k == default_metric else ""}>'
        f'{html.escape(v["label"])} ({v["unit"]})</option>'
        for k, v in metrics.items()
    )
    return (
        f'<div class="chart-box">'
        f'<div class="chart-head">'
        f'<label for="{chart_id}-metric">Metric:</label> '
        f'<select id="{chart_id}-metric">{select_options}</select>'
        f'</div>'
        f'<div class="canvas-wrap"><canvas id="{chart_id}"></canvas></div>'
        f'<script>(function(){{'
        f'const D = {data_js};'
        f'const el = document.getElementById("{chart_id}");'
        f'const sel = document.getElementById("{chart_id}-metric");'
        f'function build(metric) {{'
        f'  const spec = D.metrics[metric];'
        f'  const values = D.records.map(r => r[metric]);'
        f'  const ds = [{{'
        f'    label: spec.label + " (" + spec.unit + ")",'
        f'    data: values,'
        f'    borderColor: "rgba(66, 133, 244, 1)",'
        f'    backgroundColor: "rgba(66, 133, 244, 0.15)",'
        f'    fill: false, tension: 0.15, spanGaps: true'
        f'  }}];'
        f'  if (spec.show_yeqx) {{'
        f'    const yeqxData = spec.yeqx_field'
        f'      ? D.records.map(r => r[spec.yeqx_field]) : D.x;'
        f'    ds.push({{label: "y = x", data: yeqxData,'
        f'      borderColor: "rgba(120, 120, 120, 0.7)",'
        f'      borderDash: [4, 4], fill: false, pointRadius: 0}});'
        f'  }}'
        f'  return {{'
        f'    type: "line",'
        f'    data: {{labels: D.x, datasets: ds}},'
        f'    options: {{responsive: true, maintainAspectRatio: false,'
        f'      plugins: {{legend: {{position: "bottom",'
        f'                            labels: {{boxWidth: 12}}}}}},'
        f'      scales: {{'
        f'        x: {{title: {{display: true, text: {json.dumps(x_label)}}}}},'
        f'        y: {{beginAtZero: true,'
        f'              title: {{display: true, text: spec.unit}}}}'
        f'      }}'
        f'    }}'
        f'  }};'
        f'}}'
        f'let chart = new Chart(el, build(sel.value));'
        f'sel.addEventListener("change", () => {{'
        f'  chart.destroy(); chart = new Chart(el, build(sel.value));'
        f'}});'
        f'}})();</script>'
        f'</div>'
    )


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def _num(v):
    """Coerce to a JSON-safe number or None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return round(f, 4)


def _bridge_topics(tiers):
    seen: list[str] = []
    for t in tiers:
        for topic in t["topics"]:
            if topic not in seen:
                seen.append(topic)
    return seen


def _ms(v):
    return _num(v)


def _fmt(v):
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if f != f:
        return "n/a"
    return f"{f:.2f}"


def _json_default(o):
    if isinstance(o, float) and (o != o):
        return None
    raise TypeError(f"{type(o).__name__} not JSON serializable")


# --------------------------------------------------------------------------
# CSS / HTML templates
# --------------------------------------------------------------------------

_CSS = """
:root { color-scheme: light dark; --border: #e6e8ec;
        --bg: #f5f6f8; --surface: #ffffff; --muted: #6b7280; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #17181c; --surface: #212328; --border: #2f333a; --muted: #9ca3af; }
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  margin: 0; padding: 2rem; background: var(--bg);
  color: light-dark(#1a1a1a, #e6e6e6); line-height: 1.5;
}
main { max-width: 1200px; margin: 0 auto; }
h1 { margin: 0 0 1rem; font-size: 1.8rem; }
h2 { margin: 0 0 0.75rem; font-size: 1.35rem; }
h3 { margin: 0 0 0.75rem; font-size: 0.9rem; text-transform: uppercase;
     letter-spacing: 0.05em; color: var(--muted); }
h4 { margin: 0 0 0.5rem; font-size: 0.95rem; font-weight: 600; opacity: 0.85; }
code { font-family: SF Mono, Menlo, Consolas, monospace; font-size: 0.85rem; }

.cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem; margin-bottom: 2rem;
}
.card {
  background: var(--surface); border-radius: 8px; padding: 1rem 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card .row {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 1rem; padding: 0.35rem 0; border-bottom: 1px dashed var(--border);
  font-size: 0.88rem;
}
.card .row:last-child { border-bottom: 0; }
.card .row span { color: var(--muted); flex-shrink: 0; }
.card .row code { text-align: right; word-break: break-all; }

.badge {
  display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 500;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}
.badge.ok  { background: rgba(52, 168, 83, 0.15); color: #1e8e3e; }
.badge.bad { background: rgba(234, 67, 53, 0.15); color: #c5221f; }

section {
  background: var(--surface); border-radius: 8px; padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 2rem;
}
section > p { color: var(--muted); font-size: 0.9rem; margin: 0 0 1rem; }
.resource-block { margin-top: 1.5rem; }
.resource-block h3 { margin-top: 1.25rem; }
.resource-tbl thead tr:first-child th {
    text-align: center;
    vertical-align: middle;
}
.resource-tbl thead tr:first-child th:first-child {
    text-align: left;
}
.resource-tbl thead tr:last-child th {
    text-align: right;
    vertical-align: middle;
}

.chart-box {
  background: rgba(127, 127, 127, 0.04); border-radius: 6px;
  padding: 1rem 1rem 0.5rem; margin: 1rem 0;
}
.canvas-wrap { position: relative; height: 360px; }

table {
  border-collapse: collapse; width: 100%; margin: 1rem 0 0; font-size: 0.87rem;
  background: var(--surface);
}
table.tbl th, table.tbl td {
  padding: 0.5rem 0.75rem; text-align: right;
  border-bottom: 1px solid var(--border);
}
table.tbl th { font-weight: 600;
               background: light-dark(#f0f2f5, #2b2e34); }
/* Opt-in left alignment: `.left-N` marks the Nth column as string-valued. */
table.tbl.left-1 tr > *:nth-child(1),
table.tbl.left-2 tr > *:nth-child(2) { text-align: left; }

.chart-head {
  display: flex; align-items: center; gap: 0.5rem;
  margin-bottom: 0.75rem; font-size: 0.9rem;
}
.chart-head label { color: var(--muted); }
.chart-head select {
  font: inherit; padding: 0.25rem 0.55rem; border-radius: 4px;
  border: 1px solid var(--border); background: var(--surface);
  color: inherit; cursor: pointer;
}
"""


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAVLink → MQTT Benchmark Report</title>
<script src="{chart_cdn}"></script>
<style>{css}</style>
</head>
<body>
<main>
{header}
{sections}
</main>
</body>
</html>
"""
