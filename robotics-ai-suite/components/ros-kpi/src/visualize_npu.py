#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Intel NPU Metrics Visualizer
=============================
Reads npu_usage.log (JSON-lines produced by monitor_resources --npu) and
generates a 3-panel dashboard:

  Panel 1 – NPU Busy % over time
  Panel 2 – NPU Clock Frequency (current vs max, MHz)
  Panel 3 – NPU Memory Utilization (MB)

Metrics are read from the kernel sysfs interface:
  /sys/class/accel/accel0/device/npu_busy_time_us      (cumulative μs → delta %)
  /sys/class/accel/accel0/device/npu_current_frequency_mhz
  /sys/class/accel/accel0/device/npu_max_frequency_mhz
  /sys/class/accel/accel0/device/npu_memory_utilization (bytes)

Usage
-----
  python src/visualize_npu.py <npu_usage.log>
  python src/visualize_npu.py <npu_usage.log> --output-dir ./plots --no-show
  python src/visualize_npu.py --session 20260313_120000
  python src/visualize_npu.py  # auto-uses latest session
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

# ── Data loading ──────────────────────────────────────────────────────────────

def load_npu_log(path: str) -> List[dict]:
    """Parse JSON-lines npu_usage.log; skip start/stop event markers."""
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if 'busy_pct' in r:
                        records.append(r)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        print(f'[Error] File not found: {path}', file=sys.stderr)
    return records


def _ts(records: List[dict]) -> list:
    """Parse timestmaps from records into matplotlib-compatible dates."""
    times = []
    for r in records:
        try:
            times.append(datetime.fromisoformat(r['ts']))
        except Exception:
            times.append(None)
    return times


def _fmt_xaxis(ax, times):
    """Format x-axis as HH:MM:SS elapsed or absolute time."""
    if not times or times[0] is None:
        return
    tz0 = times[0]
    elapsed = [(t - tz0).total_seconds() if t else 0 for t in times]
    ticks = ax.get_xticks()
    ax.set_xlabel('Time (s)', fontsize=9)
    return elapsed


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(records: List[dict]):
    if not records:
        print('No NPU data records found.')
        return

    busy   = [r.get('busy_pct', 0.0) for r in records]
    freq   = [r.get('cur_freq_mhz', 0) for r in records]
    mem    = [r.get('memory_used_mb', 0.0) for r in records]

    print(f'\n── Intel NPU Summary ({len(records)} samples) ──')
    print(f'  {"Metric":<25} {"Mean":>8}  {"Max":>8}  {"Min":>8}')
    print(f'  {"-"*55}')

    def _row(label, vals):
        v = [x for x in vals if x is not None]
        if not v:
            return
        print(f'  {label:<25} {np.mean(v):>8.1f}  {np.max(v):>8.1f}  {np.min(v):>8.1f}')

    _row('NPU Busy (%)',     busy)
    _row('Frequency (MHz)',  freq)
    _row('Memory Used (MB)', mem)
    print()


# ── Legend interactivity ──────────────────────────────────────────────────────

def _wire_legend(fig, legend, handle_artists: dict):
    """Click a legend entry to toggle visibility of the corresponding line."""
    texts = legend.get_texts()
    leg_handles = getattr(legend, 'legend_handles', None) or legend.legendHandles
    entries = []
    for (_, artists), text, lh in zip(handle_artists.items(), texts, leg_handles):
        if not isinstance(artists, (list, tuple)):
            artists = [artists]
        entries.append({'text': text, 'lh': lh, 'artists': artists})

    def on_click(event):
        if event.button != 1:
            return
        for entry in entries:
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
                break

    fig.canvas.mpl_connect('button_press_event', on_click)


# ── Panels ────────────────────────────────────────────────────────────────────

def _panel_busy(ax, elapsed, records):
    busy = [r.get('busy_pct', 0.0) for r in records]
    line, = ax.plot(elapsed, busy, color='#e07b39', linewidth=1.5, label='NPU Busy %')
    ax.fill_between(elapsed, busy, alpha=0.15, color='#e07b39')
    ax.set_ylabel('Busy (%)', fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_title('NPU Busy %', fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3)
    leg = ax.legend(fontsize=8, loc='upper right')
    _wire_legend(ax.figure, leg, {'NPU Busy %': line})
    return line


def _panel_freq(ax, elapsed, records):
    cur  = [r.get('cur_freq_mhz', 0) for r in records]
    maxf = [r.get('max_freq_mhz', 0) for r in records]
    l1, = ax.plot(elapsed, cur,  color='#4c9de0', linewidth=1.5, label='Current (MHz)')
    l2, = ax.plot(elapsed, maxf, color='#b565c9', linewidth=1.0,
                  linestyle='--', alpha=0.7, label='Max (MHz)')
    ax.set_ylabel('Frequency (MHz)', fontsize=9)
    ax.set_title('NPU Clock Frequency', fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3)
    leg = ax.legend(fontsize=8, loc='upper right')
    _wire_legend(ax.figure, leg, {'Current (MHz)': l1, 'Max (MHz)': l2})


def _panel_memory(ax, elapsed, records):
    mem = [r.get('memory_used_mb', 0.0) for r in records]
    line, = ax.plot(elapsed, mem, color='#6abf6a', linewidth=1.5, label='Memory (MB)')
    ax.fill_between(elapsed, mem, alpha=0.15, color='#6abf6a')
    ax.set_ylabel('Memory (MB)', fontsize=9)
    ax.set_xlabel('Time (s)', fontsize=9)
    ax.set_title('NPU Memory Utilization', fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3)
    leg = ax.legend(fontsize=8, loc='upper right')
    _wire_legend(ax.figure, leg, {'Memory (MB)': line})


# ── Main dashboard ────────────────────────────────────────────────────────────

def plot_npu_full(records: List[dict],
                  save_path: Optional[str] = None,
                  show: bool = True,
                  title_suffix: str = '') -> Optional[str]:
    """Generate the 3-panel NPU dashboard.  Returns save path if saved."""
    if not records:
        print('[NPU Viz] No data records to plot.')
        return None

    matplotlib.use('Agg') if not show else None

    times   = _ts(records)
    t0      = times[0] if times and times[0] else datetime.now()
    elapsed = [(t - t0).total_seconds() if t else 0 for t in times]

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    fig.suptitle(f'Intel NPU Dashboard{" — " + title_suffix if title_suffix else ""}',
                 fontsize=13, fontweight='bold')
    fig.subplots_adjust(hspace=0.35, top=0.93)

    _panel_busy(axes[0], elapsed, records)
    _panel_freq(axes[1], elapsed, records)
    _panel_memory(axes[2], elapsed, records)

    axes[2].set_xlabel('Time (s)', fontsize=9)

    saved = None
    if save_path:
        fig.savefig(save_path, dpi=120, bbox_inches='tight')
        print(f'  Saved: {save_path}')
        saved = save_path

    if show:
        print('  Showing NPU dashboard – close window to continue.')
        plt.show()

    plt.close(fig)
    return saved


# ── Session discovery ─────────────────────────────────────────────────────────

def _latest_npu_log(sessions_root: str = 'monitoring_sessions') -> Optional[Path]:
    """Find the most-recent npu_usage.log under sessions_root (flat or grouped)."""
    root = Path(sessions_root)
    candidates = sorted(
        list(root.glob('[0-9]*/npu_usage.log')) +
        list(root.glob('*/[0-9]*/npu_usage.log')),
        key=lambda p: p.parent.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Intel NPU metrics visualizer (reads npu_usage.log)')
    parser.add_argument('log', nargs='?', help='Path to npu_usage.log')
    parser.add_argument('--session', metavar='NAME',
                        help='Session name (looks in monitoring_sessions/<name>/)')
    parser.add_argument('--output-dir', metavar='DIR', default=None,
                        help='Directory to save plot PNG (default: same as log)')
    parser.add_argument('--no-show', action='store_true',
                        help='Do not open interactive window (save only)')
    parser.add_argument('--no-save', action='store_true',
                        help='Do not save PNG (show only)')
    args = parser.parse_args()

    # Resolve log path
    log_path: Optional[Path] = None
    if args.log:
        log_path = Path(args.log)
    elif args.session:
        for candidate in [
            Path(f'monitoring_sessions/{args.session}/npu_usage.log'),
            *Path('monitoring_sessions').glob(f'*/{ args.session}/npu_usage.log'),
        ]:
            if candidate.exists():
                log_path = candidate
                break
        if log_path is None:
            print(f'[Error] Could not find npu_usage.log for session {args.session!r}',
                  file=sys.stderr)
            sys.exit(1)
    else:
        log_path = _latest_npu_log()
        if log_path is None:
            print('[Error] No npu_usage.log found. Run monitoring with --npu first.',
                  file=sys.stderr)
            sys.exit(1)
        print(f'Using latest NPU log: {log_path}')

    records = load_npu_log(str(log_path))
    if not records:
        print('[Error] No NPU data found in log.', file=sys.stderr)
        sys.exit(1)

    print_summary(records)

    out_dir = Path(args.output_dir) if args.output_dir else log_path.parent / 'visualizations'
    out_dir.mkdir(parents=True, exist_ok=True)

    save_path = None if args.no_save else str(out_dir / 'npu_dashboard.png')
    show      = not args.no_show

    print('Generating NPU dashboard...')
    plot_npu_full(
        records,
        save_path=save_path,
        show=show,
        title_suffix=log_path.parent.name,
    )
    print('Done.')


if __name__ == '__main__':
    main()
