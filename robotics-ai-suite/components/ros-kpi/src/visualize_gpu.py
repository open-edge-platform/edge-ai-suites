#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Intel GPU Metrics Visualizer
=============================
Reads gpu_usage.log (JSON-lines produced by monitor_resources --gpu or
gpu_pid_analyzer.py) and generates a multi-panel plot with:

  Panel 1 – GPU Busy % (overall) + per-engine-class overlay
            (Render/3D  Blitter  Video  VE/VideoEnhance)
  Panel 2 – GT Frequency: actual vs requested (MHz)  + RC6 residency %
  Panel 3 – GPU Temperature (°C)          [if temp_c field present]
  Panel 4 – Power: GPU (W) + Package (W)  [if power fields present]
  Panel 5 – Per-PID GPU usage (top N)     [if clients field present]

Both intel_gpu_top (rich) records and sysfs-fallback records are handled.
Engine keys in the log may be raw ("Render/3D 0") or canonical ("Render/3D");
both are mapped to the four canonical classes automatically.

Usage
-----
  python src/visualize_gpu.py <gpu_usage.log>
  python src/visualize_gpu.py <gpu_usage.log> --save --output-dir ./plots
  python src/visualize_gpu.py <gpu_usage.log> --show  --top 8
  python src/visualize_gpu.py --session 20260312_134253
  python src/visualize_gpu.py  # auto-uses latest session
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Engine-class mapping  (canonical label → regex)
# ──────────────────────────────────────────────────────────────────────────────

_ENGINE_CLASSES: Dict[str, re.Pattern] = {
    'Render/3D': re.compile(r'render|3d',                      re.I),
    'Blitter':   re.compile(r'blitter|blt',                    re.I),
    'Video':     re.compile(r'^video$',                        re.I),
    'VE':        re.compile(r'videoenhance|video_enhance|ve\b', re.I),
}
_ENG_COLORS = {
    'Render/3D': '#e07b39',
    'Blitter':   '#4c9de0',
    'Video':     '#6abf6a',
    'VE':        '#b565c9',
}


def _classify_engine_key(key: str) -> Optional[str]:
    """Return canonical class name for a raw engine key, or None if unknown."""
    for cls, pat in _ENGINE_CLASSES.items():
        if pat.search(key):
            return cls
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────

def load_gpu_log(path: str) -> List[dict]:
    """
    Parse a JSON-lines gpu_usage.log.  Returns only data records
    (skips 'start'/'stop' event markers).
    """
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if 'busy_pct' in r or 'act_freq_mhz' in r:
                        records.append(r)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        print(f'[Error] File not found: {path}', file=sys.stderr)
    return records


def _canonical_engines(record: dict) -> Dict[str, Dict[str, float]]:
    """
    Normalise the 'engines' field of a record to canonical class names.
    Engine values can be:
      • {busy, sema, wait}  dicts (raw key names from monitor_resources)
      • float               (busy only, from some older formats)
    Returns {canonical_class: {busy, sema, wait}} summed across instances.
    """
    eng_raw = record.get('engines') or {}
    out: Dict[str, Dict[str, float]] = {
        k: {'busy': 0.0, 'sema': 0.0, 'wait': 0.0} for k in _ENGINE_CLASSES
    }
    for key, val in eng_raw.items():
        if isinstance(val, dict):
            busy = float(val.get('busy', 0))
            sema = float(val.get('sema', 0))
            wait = float(val.get('wait', 0))
        elif isinstance(val, (int, float)):
            busy, sema, wait = float(val), 0.0, 0.0
        else:
            continue
        cls = _classify_engine_key(key)
        if cls:
            out[cls]['busy'] += busy
            out[cls]['sema'] += sema
            out[cls]['wait'] += wait
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Summary printer
# ──────────────────────────────────────────────────────────────────────────────

def print_summary(records: List[dict]):
    if not records:
        print('  No GPU data.')
        return
    source = records[0].get('source', 'sysfs')
    n = len(records)
    busy = [r.get('busy_pct', 0) for r in records]
    freq = [r.get('act_freq_mhz', 0) for r in records]
    temps = [r['temp_c'] for r in records if r.get('temp_c') is not None]
    pwr_g = [r.get('power_gpu_w', 0) for r in records]
    pwr_p = [r.get('power_pkg_w', 0) for r in records]
    rc6   = [r.get('rc6_pct', 0) for r in records]

    print(f'\n{"═"*60}')
    print(f'  Intel GPU Summary  ({source})  –  {n} samples')
    print(f'{"═"*60}')
    print(f'  Busy %   : avg={sum(busy)/n:.1f}  max={max(busy):.1f}  min={min(busy):.1f}')
    print(f'  Freq MHz : avg={sum(freq)/n:.0f}  max={max(freq)}  min={min(freq)}')
    if temps:
        print(f'  Temp °C  : avg={sum(temps)/len(temps):.1f}  max={max(temps):.1f}  min={min(temps):.1f}')
    if any(p > 0 for p in pwr_g):
        print(f'  GPU W    : avg={sum(pwr_g)/n:.2f}  max={max(pwr_g):.2f}')
    if any(p > 0 for p in pwr_p):
        print(f'  Pkg W    : avg={sum(pwr_p)/n:.2f}  max={max(pwr_p):.2f}')
    if rc6:
        print(f'  RC6 %    : avg={sum(rc6)/n:.1f}')

    if source == 'intel_gpu_top':
        print(f'\n  Engine-class averages:')
        for cls in _ENGINE_CLASSES:
            vals = [_canonical_engines(r)[cls]['busy'] for r in records]
            print(f'    {cls:<12}: avg={sum(vals)/n:.1f}%  max={max(vals):.1f}%')

    # Per-PID summary
    pid_totals: Dict[int, list] = defaultdict(list)
    pid_names:  Dict[int, str]  = {}
    for r in records:
        for c in (r.get('clients') or []):
            pid_totals[c['pid']].append(c['total'])
            pid_names[c['pid']] = c.get('name', '?')
    if pid_totals:
        top = sorted(pid_totals.items(),
                     key=lambda kv: sum(kv[1]) / len(kv[1]),
                     reverse=True)[:10]
        print(f'\n  Top PIDs by avg GPU %:')
        for pid, vals in top:
            print(f'    PID {pid:<7} {pid_names[pid]:<28}  avg={sum(vals)/len(vals):.1f}%  max={max(vals):.1f}%')
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Plot helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ts(records: List[dict]) -> list:
    return [datetime.fromisoformat(r['ts']) for r in records]


def _fmt_xaxis(ax, times):
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    if len(times) > 1:
        span = (times[-1] - times[0]).total_seconds()
        if span < 120:
            ax.xaxis.set_major_locator(mdates.SecondLocator(interval=10))
        elif span < 600:
            ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
        else:
            ax.xaxis.set_major_locator(mdates.MinuteLocator())


def _legend_handles(leg):
    """Compatibility shim: legend.legend_handles (mpl ≥ 3.5) or legendHandles."""
    return getattr(leg, 'legend_handles', None) or leg.legendHandles


def _wire_legend(fig, legend, handle_artists):
    """
    Make legend entries clickable to toggle artist visibility.
    Clicking EITHER the coloured marker OR the text label works.

    Uses button_press_event + contains() rather than the picker mechanism,
    which is unreliable for Patch/PolyCollection proxies and twinx legends.
    """
    texts = legend.get_texts()
    leg_handles_list = _legend_handles(legend)

    # Build an entry list parallel to the legend rows
    entries = []
    for (_, data_artists), text, lh in zip(handle_artists.items(), texts, leg_handles_list):
        if not isinstance(data_artists, (list, tuple)):
            data_artists = [data_artists]
        entries.append({'text': text, 'lh': lh, 'artists': data_artists})

    def on_click(event):
        if event.button != 1:          # left-click only
            return
        for entry in entries:
            # Check if the click landed on the text label or the handle marker
            hit_text, _ = entry['text'].contains(event)
            try:
                hit_handle, _ = entry['lh'].contains(event)
            except Exception:
                hit_handle = False
            if hit_text or hit_handle:
                visible = not entry['artists'][0].get_visible()
                for a in entry['artists']:
                    a.set_visible(visible)
                alpha = 1.0 if visible else 0.2
                entry['text'].set_alpha(alpha)
                try:
                    entry['lh'].set_alpha(alpha)
                except Exception:
                    pass
                fig.canvas.draw()
                break   # only one entry per click

    fig.canvas.mpl_connect('button_press_event', on_click)


# ──────────────────────────────────────────────────────────────────────────────
# Individual panels
# ──────────────────────────────────────────────────────────────────────────────

def _panel_engines(ax, times, records):
    """Panel 1: GPU overall busy + per-engine-class lines."""
    busy = [r.get('busy_pct', 0.0) for r in records]
    fill_busy = ax.fill_between(times, busy, alpha=0.12, color='steelblue')
    line_busy, = ax.plot(times, busy, color='steelblue', linewidth=1.8, label='Overall busy %')

    source = records[0].get('source', 'sysfs')
    has_engines = source == 'intel_gpu_top' and any(r.get('engines') for r in records)
    engine_lines = []
    if has_engines:
        for cls in _ENGINE_CLASSES:
            vals = [_canonical_engines(r)[cls]['busy'] for r in records]
            if any(v > 0.05 for v in vals):
                line, = ax.plot(times, vals, linewidth=1.1, linestyle='--',
                                color=_ENG_COLORS[cls], label=f'{cls} busy %', alpha=0.8)
                engine_lines.append(line)

    ax.set_ylabel('GPU Busy (%)', fontsize=9)
    ax.set_ylim(-2, 108)
    ax.grid(True, alpha=0.25)
    _fmt_xaxis(ax, times)
    leg = ax.legend(loc='upper right', fontsize=7, ncol=2)

    handles = _legend_handles(leg)
    handle_map = {}
    if handles:
        handle_map[handles[0]] = [fill_busy, line_busy]
        for h, ln in zip(handles[1:], engine_lines):
            handle_map[h] = ln
    _wire_legend(ax.get_figure(), leg, handle_map)


def _panel_engines_stacked(ax, times, records):
    """Alternative Panel 1: stacked area for engine classes when all add up to ~100%."""
    source = records[0].get('source', 'sysfs')
    has_engines = source == 'intel_gpu_top' and any(r.get('engines') for r in records)
    if not has_engines:
        _panel_engines(ax, times, records)
        return

    cls_vals = {}
    for cls in _ENGINE_CLASSES:
        vals = [_canonical_engines(r)[cls]['busy'] for r in records]
        cls_vals[cls] = vals

    # If stacked max never exceeds 105% use stacked fill, else fall back to lines
    stacked = [sum(cls_vals[c][i] for c in _ENGINE_CLASSES) for i in range(len(records))]
    if max(stacked, default=0) <= 105:
        y_stack = np.zeros(len(records))
        poly_map = {}
        for cls in _ENGINE_CLASSES:
            vals = np.array(cls_vals[cls])
            poly = ax.fill_between(times, y_stack, y_stack + vals,
                                   alpha=0.55, color=_ENG_COLORS[cls], label=cls)
            poly_map[cls] = poly
            y_stack += vals
    else:
        _panel_engines(ax, times, records)
        return

    ax.set_ylabel('Engine Busy (%)', fontsize=9)
    ax.set_ylim(-2, 108)
    ax.grid(True, alpha=0.25)
    _fmt_xaxis(ax, times)
    leg = ax.legend(loc='upper right', fontsize=7, ncol=2)

    handles = _legend_handles(leg)
    # Legend order matches the _ENGINE_CLASSES forward-iteration order
    handle_map = {h: poly_map[cls]
                  for h, cls in zip(handles, _ENGINE_CLASSES)
                  if cls in poly_map}
    _wire_legend(ax.get_figure(), leg, handle_map)


def _panel_freq(ax, times, records):
    """Panel 2: Frequency + RC6."""
    source = records[0].get('source', 'sysfs')
    act_freq = [r.get('act_freq_mhz', 0) for r in records]
    fig = ax.get_figure()

    if source == 'intel_gpu_top':
        req_freq = [r.get('req_freq_mhz', 0) for r in records]
        rc6_pct  = [r.get('rc6_pct', 0.0) for r in records]
        line_act, = ax.plot(times, act_freq, color='darkorange', linewidth=1.3, label='Actual freq')
        line_req, = ax.plot(times, req_freq, color='#f0c040', linewidth=1.0, linestyle='--',
                            label='Requested freq')
        ax.set_ylabel('Frequency (MHz)', fontsize=9)
        ax2_rc6 = ax.twinx()
        line_rc6, = ax2_rc6.plot(times, rc6_pct, color='#888', linewidth=0.8,
                                 linestyle=':', label='RC6 %', alpha=0.7)
        ax2_rc6.set_ylabel('RC6 (%)', fontsize=8, color='#888')
        ax2_rc6.tick_params(axis='y', labelcolor='#888')
        lines, labels = ax.get_legend_handles_labels()
        l2, lb2 = ax2_rc6.get_legend_handles_labels()
        leg = ax.legend(lines + l2, labels + lb2, loc='upper right', fontsize=7)
        handles = _legend_handles(leg)
        handle_map = {h: ln for h, ln in zip(handles, [line_act, line_req, line_rc6])}
        _wire_legend(fig, leg, handle_map)
    else:
        cur_freq = [r.get('cur_freq_mhz', 0) for r in records]
        max_freq = [r.get('max_freq_mhz', 0) for r in records]
        line_act, = ax.plot(times, act_freq, color='darkorange', linewidth=1.3, label='Actual freq')
        line_cur, = ax.plot(times, cur_freq, color='#f0c040', linewidth=1.0, linestyle='--',
                            label='Current freq')
        sysfs_lines = [line_act, line_cur]
        if any(m > 0 for m in max_freq):
            line_max, = ax.plot(times, max_freq, color='lightcoral', linewidth=0.8,
                                linestyle=':', label='Max freq')
            sysfs_lines.append(line_max)
        leg = ax.legend(loc='upper right', fontsize=7)
        handles = _legend_handles(leg)
        handle_map = {h: ln for h, ln in zip(handles, sysfs_lines)}
        _wire_legend(fig, leg, handle_map)
        ax.set_ylabel('Frequency (MHz)', fontsize=9)

    ax.grid(True, alpha=0.25)
    _fmt_xaxis(ax, times)


def _panel_temp(ax, times, records):
    """Panel 3: GPU temperature."""
    temps = [r.get('temp_c') for r in records]
    pairs = [(t, v) for t, v in zip(times, temps) if v is not None]
    if not pairs:
        ax.text(0.5, 0.5, 'Temperature data not available',
                ha='center', va='center', transform=ax.transAxes, fontsize=9, color='grey')
        ax.set_ylabel('Temp (°C)', fontsize=9)
        return
    ts_t, vals_t = zip(*pairs)
    fill_t = ax.fill_between(ts_t, vals_t, alpha=0.2, color='tomato')
    line_t, = ax.plot(ts_t, vals_t, color='tomato', linewidth=1.3, label='GPU Temp (°C)')
    # Danger line at 90 °C
    has_thresh = max(vals_t) > 70
    if has_thresh:
        line_thresh = ax.axhline(90, color='red', linewidth=0.8, linestyle='--',
                                 alpha=0.5, label='90 °C threshold')
    ax.set_ylabel('Temp (°C)', fontsize=9)
    leg = ax.legend(loc='upper right', fontsize=7)
    handles = _legend_handles(leg)
    handle_map = {}
    if handles:
        handle_map[handles[0]] = [fill_t, line_t]
        if has_thresh and len(handles) > 1:
            handle_map[handles[1]] = line_thresh
    _wire_legend(ax.get_figure(), leg, handle_map)
    ax.grid(True, alpha=0.25)
    _fmt_xaxis(ax, ts_t)


def _panel_power(ax, times, records):
    """Panel 4: GPU & Package power."""
    gpu_w = [r.get('power_gpu_w', 0.0) for r in records]
    pkg_w = [r.get('power_pkg_w', 0.0) for r in records]
    fill_gpu = ax.fill_between(times, gpu_w, alpha=0.2, color='crimson')
    line_gpu, = ax.plot(times, gpu_w, color='crimson', linewidth=1.3, label='GPU (W)')
    power_artists = [[fill_gpu, line_gpu]]
    if any(p > 0 for p in pkg_w):
        line_pkg, = ax.plot(times, pkg_w, color='salmon', linewidth=1.0, linestyle='--',
                            label='Package (W)')
        power_artists.append(line_pkg)
    ax.set_ylabel('Power (W)', fontsize=9)
    leg = ax.legend(loc='upper right', fontsize=7)
    handles = _legend_handles(leg)
    handle_map = {h: a for h, a in zip(handles, power_artists)}
    _wire_legend(ax.get_figure(), leg, handle_map)
    ax.grid(True, alpha=0.25)
    _fmt_xaxis(ax, times)


def _panel_pids(ax, times, records, top_n: int = 8):
    """Panel 5: Per-PID GPU busy% over time (top N by peak)."""
    # Aggregate per PID: list of (timestamp, total_busy%)
    pid_series: Dict[int, List[Tuple[datetime, float]]] = defaultdict(list)
    pid_names:  Dict[int, str] = {}
    for r, ts in zip(records, times):
        for c in (r.get('clients') or []):
            pid = c['pid']
            pid_series[pid].append((ts, c['total']))
            pid_names[pid] = c.get('name', '?')

    if not pid_series:
        ax.text(0.5, 0.5,
                'Per-PID data not available\n'
                '(requires intel_gpu_top ≥ 1.27 + CAP_PERFMON)',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=9, color='grey', multialignment='center')
        ax.set_ylabel('GPU per-PID (%)', fontsize=9)
        return

    # Pick top N by peak busy%
    peak = {pid: max(v for _, v in pts) for pid, pts in pid_series.items()}
    top_pids = sorted(peak, key=peak.__getitem__, reverse=True)[:top_n]

    colors = plt.cm.tab10.colors
    pid_lines = []
    for i, pid in enumerate(top_pids):
        pts = sorted(pid_series[pid])
        ts_pid = [p[0] for p in pts]
        vs_pid = [p[1] for p in pts]
        label = f'PID {pid} ({pid_names[pid]})'
        line, = ax.plot(ts_pid, vs_pid, linewidth=1.0, label=label,
                        color=colors[i % len(colors)], alpha=0.85)
        pid_lines.append(line)

    ax.set_ylabel('GPU per-PID (%)', fontsize=9)
    ax.set_ylim(-1, max(peak[p] for p in top_pids) * 1.15 + 1)
    ax.grid(True, alpha=0.25)
    _fmt_xaxis(ax, times)
    leg = ax.legend(loc='upper right', fontsize=7, ncol=2)
    handles = _legend_handles(leg)
    handle_map = {h: ln for h, ln in zip(handles, pid_lines)}
    _wire_legend(ax.get_figure(), leg, handle_map)


# ──────────────────────────────────────────────────────────────────────────────
# Stacked-bar per-engine breakdwon per PID (static snapshot chart)
# ──────────────────────────────────────────────────────────────────────────────

def plot_pid_engine_breakdown(records: List[dict],
                              top_n: int = 12,
                              output_file: str = None,
                              show: bool = False):
    """
    Horizontal stacked-bar chart: one bar per PID showing average % per
    engine class.  Shows only at the end of the session (avg across all
    samples where that PID appeared).
    """
    pid_eng_sums: Dict[int, Dict[str, float]] = defaultdict(
        lambda: {c: 0.0 for c in _ENGINE_CLASSES})
    pid_counts: Dict[int, int] = defaultdict(int)
    pid_names:  Dict[int, str] = {}

    for r in records:
        for c in (r.get('clients') or []):
            pid = c['pid']
            pid_names[pid] = c.get('name', '?')
            pid_counts[pid] += 1
            for cls in _ENGINE_CLASSES:
                pid_eng_sums[pid][cls] += c.get('engines', {}).get(cls, 0.0)

    if not pid_eng_sums:
        return  # nothing to show

    # Compute averages, keep top N by total GPU%
    pid_avg: Dict[int, Dict[str, float]] = {}
    for pid, sums in pid_eng_sums.items():
        n = pid_counts[pid]
        pid_avg[pid] = {cls: sums[cls] / n for cls in _ENGINE_CLASSES}

    top_pids = sorted(pid_avg, key=lambda p: sum(pid_avg[p].values()),
                      reverse=True)[:top_n]
    # Build matrix
    labels = [f'PID {p}\n{pid_names[p][:18]}' for p in top_pids]
    fig, ax = plt.subplots(figsize=(12, max(4, len(top_pids) * 0.55 + 2)))
    y_pos = np.arange(len(top_pids))
    left = np.zeros(len(top_pids))

    cls_order = list(reversed(list(_ENGINE_CLASSES)))   # order of barh() calls
    eng_patches = {}   # cls → [Rectangle]
    eng_texts   = {}   # cls → [Text]  (bar value labels)

    for cls in cls_order:
        vals = np.array([pid_avg[p][cls] for p in top_pids])
        bars = ax.barh(y_pos, vals, left=left, label=cls,
                       color=_ENG_COLORS[cls], alpha=0.8, height=0.65)
        eng_patches[cls] = list(bars)
        eng_texts[cls] = []
        for bar, v in zip(bars, vals):
            if v >= 1.0:
                cx = bar.get_x() + bar.get_width() / 2
                txt = ax.text(cx, bar.get_y() + bar.get_height() / 2,
                              f'{v:.1f}%', ha='center', va='center',
                              fontsize=7, color='black')
                eng_texts[cls].append(txt)
        left += vals

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel('Average GPU Engine Busy (%)', fontsize=10)
    ax.set_title(
        f'Per-PID GPU Engine-Class Breakdown  (avg across session, top {len(top_pids)})',
        fontsize=12, fontweight='bold')
    leg = ax.legend(loc='lower right', fontsize=8)
    handles = _legend_handles(leg)
    handle_map = {h: eng_patches[c] + eng_texts[c]
                  for h, c in zip(handles, cls_order) if c in eng_patches}
    _wire_legend(fig, leg, handle_map)
    ax.grid(True, alpha=0.2, axis='x')
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f'  Saved: {output_file}')
        if not show:
            plt.close()
    if show:
        plt.show()
        plt.close()


# ──────────────────────────────────────────────────────────────────────────────
# Main combined plot
# ──────────────────────────────────────────────────────────────────────────────

def plot_gpu_full(records: List[dict],
                  output_file: str = None,
                  show: bool = False,
                  stacked_engines: bool = True,
                  top_pids: int = 8):
    """
    Render the full multi-panel GPU dashboard and optionally save to file.

    Panels included dynamically:
      1  Engine-class busy % (always)
      2  Frequency + RC6 (always)
      3  Temperature (if temp_c field present in at least one record)
      4  Power (if power_gpu_w field present)
      5  Per-PID GPU % over time (if clients present)
    """
    if not records:
        print('  No GPU records to plot.')
        return

    source      = records[0].get('source', 'sysfs')
    has_temp    = any(r.get('temp_c') is not None for r in records)
    has_power   = source == 'intel_gpu_top' and any(r.get('power_gpu_w', 0) for r in records)
    has_clients = any(r.get('clients') for r in records)

    nrows = 2 + has_temp + has_power + has_clients
    fig, axes = plt.subplots(nrows, 1,
                             figsize=(15, 3.8 * nrows),
                             sharex=False)
    axes = list(axes) if nrows > 1 else [axes]

    times = _ts(records)
    session_range = ''
    if times:
        session_range = (f'{times[0].strftime("%H:%M:%S")} – '
                         f'{times[-1].strftime("%H:%M:%S")}  '
                         f'({len(records)} samples)')

    title_parts = [f'Intel GPU  [{source}]']
    if session_range:
        title_parts.append(session_range)
    fig.suptitle('\n'.join(title_parts), fontsize=13, fontweight='bold', y=0.995)
    fig.subplots_adjust(top=0.96, hspace=0.38)

    ax_iter = iter(axes)

    # Panel 1 – engines
    ax1 = next(ax_iter)
    if stacked_engines:
        _panel_engines_stacked(ax1, times, records)
        ax1.set_title('Engine-Class Busy %  (stacked · click legend to toggle)',
                      fontsize=9, pad=3)
    else:
        _panel_engines(ax1, times, records)
        ax1.set_title('Engine-Class Busy %  (click legend to toggle)', fontsize=9, pad=3)

    # Panel 2 – frequency
    ax2 = next(ax_iter)
    _panel_freq(ax2, times, records)
    ax2.set_title('GT Frequency (MHz) + RC6 Residency %', fontsize=9, pad=3)

    # Panel 3 – temperature (conditional)
    if has_temp:
        ax3 = next(ax_iter)
        _panel_temp(ax3, times, records)
        ax3.set_title('GPU Temperature', fontsize=9, pad=3)

    # Panel 4 – power (conditional)
    if has_power:
        ax4 = next(ax_iter)
        _panel_power(ax4, times, records)
        ax4.set_title('GPU & Package Power', fontsize=9, pad=3)

    # Panel 5 – per-PID (conditional)
    if has_clients:
        ax5 = next(ax_iter)
        _panel_pids(ax5, times, records, top_n=top_pids)
        ax5.set_title(f'Per-PID GPU Busy %  (top {top_pids}, click legend to toggle)',
                      fontsize=9, pad=3)

    # Label the last axis with time
    axes[-1].set_xlabel('Time (HH:MM:SS)', fontsize=9)
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=30, ha='right')

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f'  Saved: {output_file}')
        if not show:
            plt.close(fig)
    if show:
        print('  Showing GPU dashboard – close window to continue.')
        plt.show()
        plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _latest_session_dir(sessions_root: str = 'monitoring_sessions') -> Optional[Path]:
    root = Path(sessions_root)
    if not root.exists():
        return None
    dirs = sorted(root.glob('[0-9]*/'), reverse=True)
    return dirs[0] if dirs else None


def main():
    parser = argparse.ArgumentParser(
        description='Visualize Intel GPU metrics from gpu_usage.log',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('log_file', nargs='?', default=None,
                        help='Path to gpu_usage.log (auto-detected from latest session'
                             ' if omitted)')
    parser.add_argument('--session', '-s', default=None,
                        help='Session name to find gpu_usage.log '
                             '(e.g. 20260312_134253)')
    parser.add_argument('--sessions-dir', default='monitoring_sessions',
                        help='Root directory for sessions (default: monitoring_sessions)')
    parser.add_argument('--output-dir', '-o', default=None,
                        help='Directory to write PNG files (no PNGs saved unless specified)')
    parser.add_argument('--save', action='store_true',
                        help='Save PNG to the session visualizations/ dir '
                             '(auto-sets --output-dir if not given)')
    parser.add_argument('--show', action='store_true',
                        help='Open interactive matplotlib windows')
    parser.add_argument('--no-show', action='store_true',
                        help='Never open windows (useful in headless CI)')
    parser.add_argument('--top', type=int, default=8, metavar='N',
                        help='Top N PIDs to show in per-PID panels (default: 8)')
    parser.add_argument('--lines', action='store_true',
                        help='Use line-overlay mode for engine panel instead of stacked fill')
    parser.add_argument('--summary', action='store_true',
                        help='Print summary statistics and exit (no plots)')
    parser.add_argument('--pid-bar', action='store_true',
                        help='Also generate per-PID engine-class bar chart')
    args = parser.parse_args()

    # ── Resolve log file path ───────────────────────────────────────────────
    log_path: Optional[Path] = None
    vis_dir:  Optional[Path] = None

    if args.log_file:
        log_path = Path(args.log_file)
    elif args.session:
        sess_dir = Path(args.sessions_dir) / args.session
        log_path = sess_dir / 'gpu_usage.log'
        vis_dir  = sess_dir / 'visualizations'
    else:
        sess_dir = _latest_session_dir(args.sessions_dir)
        if sess_dir:
            log_path = sess_dir / 'gpu_usage.log'
            vis_dir  = sess_dir / 'visualizations'

    if log_path is None or not log_path.exists():
        errmsg = (
            f'gpu_usage.log not found at {log_path}.\n'
            'Run:  make monitor-gpu  or  make monitor-remote REMOTE_IP=<ip> GPU=1\n'
            'Then: make visualize-gpu'
        )
        print(f'[Error] {errmsg}', file=sys.stderr)
        sys.exit(1)

    print(f'Loading: {log_path}')
    records = load_gpu_log(str(log_path))
    if not records:
        print('[Error] No GPU data records found in the log.', file=sys.stderr)
        sys.exit(1)

    print(f'  {len(records)} data records  '
          f'(source: {records[0].get("source", "unknown")})')

    # ── Summary ─────────────────────────────────────────────────────────────
    print_summary(records)

    if args.summary:
        return

    # ── Output paths ────────────────────────────────────────────────────────
    out_dir: Optional[Path] = None
    if args.output_dir:
        out_dir = Path(args.output_dir)
    elif args.save and vis_dir:
        out_dir = vis_dir
    elif args.save:
        out_dir = log_path.parent / 'visualizations'

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    show = args.show and not args.no_show

    # ── Main dashboard ──────────────────────────────────────────────────────
    main_out = str(out_dir / 'gpu_dashboard.png') if out_dir else None
    print('Generating GPU dashboard...')
    plot_gpu_full(records,
                  output_file=main_out,
                  show=show,
                  stacked_engines=not args.lines,
                  top_pids=args.top)

    # ── Per-PID bar chart (optional) ─────────────────────────────────────────
    if args.pid_bar and any(r.get('clients') for r in records):
        bar_out = str(out_dir / 'gpu_pid_engine_breakdown.png') if out_dir else None
        print('Generating per-PID engine-class bar chart...')
        plot_pid_engine_breakdown(records,
                                  top_n=args.top,
                                  output_file=bar_out,
                                  show=show)

    if not show and not out_dir:
        # No output requested – open window anyway so user sees something
        print('No --output-dir or --show specified; opening interactive window.')
        plt.show()

    print('Done.')


if __name__ == '__main__':
    main()
