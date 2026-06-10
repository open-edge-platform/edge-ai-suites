#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Thermal & Throttle Visualizer
==============================
Reads cpu_power.log (and optionally gpu_usage.log) produced by
monitor_resources.py and generates a multi-panel thermal dashboard:

  Panel 1 - CPU + GPU Temperature (°C)   [with 95 °C warning line]
  Panel 2 - CPU & GPU Throttle State     [binary step-fill: 1 = throttled]
  Panel 3 - CPU Package Power (W)        [if power data present]

Both logs are JSON-lines.  Missing fields are handled gracefully so the
plot degrades cleanly when only one log is available.

Usage
-----
  python src/visualize_thermal.py <session_dir>
  python src/visualize_thermal.py --session monitoring_sessions/wandering/20260513_003015
  python src/visualize_thermal.py  # auto-uses latest session with cpu_power.log
  python src/visualize_thermal.py cpu_power.log [--gpu-log gpu_usage.log]
  python src/visualize_thermal.py <session_dir> --save
  python src/visualize_thermal.py <session_dir> --show
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib.dates as mdates   # pylint: disable=import-error
import matplotlib.pyplot as plt     # pylint: disable=import-error

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

WARN_TEMP_C = 90.0   # °C – warning line drawn on temp panel

# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────


def _load_jsonl(path: Path, key_required: str) -> List[dict]:
    """Load JSON-lines from *path*, keeping only records that contain *key_required*."""
    records: List[dict] = []
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if key_required in r:
                        records.append(r)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        print(f'[Warning] File not found: {path}', file=sys.stderr)
    return records


def load_cpu_power_log(path: Path) -> List[dict]:
    """Load cpu_power.log; each record has ts, power_w, temp_c, throttled."""
    return _load_jsonl(path, 'power_w')


def load_gpu_log(path: Optional[Path]) -> List[dict]:
    """Load gpu_usage.log; each record has ts, busy_pct, throttled, optionally temp_c."""
    if path is None or not path.exists():
        return []
    return _load_jsonl(path, 'busy_pct')


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

def print_summary(cpu_records: List[dict], gpu_records: List[dict]):
    """Print a short text summary of thermal and throttle data."""
    print(f'\n{"═" * 60}')
    print('  Thermal & Throttle Summary')
    print(f'{"═" * 60}')

    if cpu_records:
        n = len(cpu_records)
        temps = [r['temp_c'] for r in cpu_records if r.get('temp_c') is not None]
        pwrs  = [r['power_w'] for r in cpu_records if r.get('power_w') is not None]
        throttled = [r for r in cpu_records if r.get('throttled')]
        pct_thr = 100.0 * len(throttled) / n if n else 0.0

        print(f'\n  CPU  ({n} samples)')
        if temps:
            print(f'    Temp °C   : avg={sum(temps)/len(temps):.1f}  '
                  f'max={max(temps):.1f}  min={min(temps):.1f}')
        if pwrs:
            print(f'    Power W   : avg={sum(pwrs)/len(pwrs):.2f}  '
                  f'max={max(pwrs):.2f}  min={min(pwrs):.2f}')
        print(f'    Throttled : {len(throttled)}/{n} samples  ({pct_thr:.1f} %)')
        if temps and max(temps) >= WARN_TEMP_C:
            print(f'    ⚠  CPU exceeded {WARN_TEMP_C:.0f} °C warning threshold!')

    if gpu_records:
        n = len(gpu_records)
        temps = [r['temp_c'] for r in gpu_records if r.get('temp_c') is not None]
        throttled = [r for r in gpu_records if r.get('throttled')]
        pct_thr = 100.0 * len(throttled) / n if n else 0.0

        print(f'\n  GPU  ({n} samples)')
        if temps:
            print(f'    Temp °C   : avg={sum(temps)/len(temps):.1f}  '
                  f'max={max(temps):.1f}  min={min(temps):.1f}')
        else:
            print('    Temp °C   : not available in log')
        print(f'    Throttled : {len(throttled)}/{n} samples  ({pct_thr:.1f} %)')

    print()


# ──────────────────────────────────────────────────────────────────────────────
# Plot helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_times(records: List[dict]) -> List[datetime]:
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
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')


# ──────────────────────────────────────────────────────────────────────────────
# Panel implementations
# ──────────────────────────────────────────────────────────────────────────────

def _panel_temperature(ax, cpu_records: List[dict], gpu_records: List[dict]):
    """Panel 1 – CPU and GPU temperature time-series."""
    plotted = False

    if cpu_records:
        cpu_times = _parse_times(cpu_records)
        cpu_temps = [r.get('temp_c') for r in cpu_records]
        pairs = [(t, v) for t, v in zip(cpu_times, cpu_temps) if v is not None]
        if pairs:
            ts, vals = zip(*pairs)
            ax.plot(ts, vals, color='#f97316', linewidth=1.4,
                    label='CPU pkg temp (°C)')
            plotted = True

    if gpu_records:
        gpu_times = _parse_times(gpu_records)
        gpu_temps = [r.get('temp_c') for r in gpu_records]
        pairs = [(t, v) for t, v in zip(gpu_times, gpu_temps) if v is not None]
        if pairs:
            ts, vals = zip(*pairs)
            ax.plot(ts, vals, color='#ef4444', linewidth=1.4,
                    label='GPU temp (°C)')
            plotted = True

    if not plotted:
        ax.text(0.5, 0.5, 'Temperature data not available\n'
                '(run monitor_resources.py with --power --gpu)',
                transform=ax.transAxes, ha='center', va='center',
                fontsize=10, color='grey')
    else:
        ax.axhline(WARN_TEMP_C, color='red', linestyle='--', linewidth=1.0,
                   alpha=0.7, label=f'{WARN_TEMP_C:.0f} °C warning')
        ax.set_ylim(bottom=0)
        ax.legend(loc='upper left', fontsize=8)

    ax.set_ylabel('Temperature (°C)', fontsize=9)
    ax.grid(True, alpha=0.25)


def _panel_throttle(ax, cpu_records: List[dict], gpu_records: List[dict]):
    """
    Panel 2 – CPU and GPU throttle state as binary step-fills.

    CPU throttle: orange fill in the upper half (0.5 – 1.0).
    GPU throttle: red fill in the lower half (0.0 – 0.5).
    Value = 1 when throttled, 0 when not.
    """
    any_data = False

    def _step_values(records: List[dict]) -> Tuple[list, list]:
        """Return (times, 0/1 values) for throttle state; None mapped to 0."""
        times = _parse_times(records)
        vals = [1 if r.get('throttled') else 0 for r in records]
        return times, vals

    if cpu_records:
        times, vals = _step_values(cpu_records)
        if times:
            # Scale CPU throttle to upper half: 0→0.5, 1→1.0
            scaled = [0.5 + 0.5 * v for v in vals]
            ax.fill_between(times, 0.5, scaled,
                            step='post', alpha=0.65, color='#f97316',
                            label='CPU throttled')
            ax.step(times, scaled, where='post', color='#f97316',
                    linewidth=0.8, alpha=0.9)
            any_data = True

    if gpu_records:
        times, vals = _step_values(gpu_records)
        if times:
            # Scale GPU throttle to lower half: 0→0.0, 1→0.5
            scaled = [0.5 * v for v in vals]
            ax.fill_between(times, 0.0, scaled,
                            step='post', alpha=0.65, color='#ef4444',
                            label='GPU throttled')
            ax.step(times, scaled, where='post', color='#ef4444',
                    linewidth=0.8, alpha=0.9)
            any_data = True

    ax.set_ylim(-0.05, 1.1)
    ax.set_yticks([0.25, 0.75])
    ax.set_yticklabels(['GPU', 'CPU'], fontsize=9)
    ax.axhline(0.5, color='grey', linewidth=0.5, alpha=0.5)

    if any_data:
        ax.legend(loc='upper right', fontsize=8)
    else:
        ax.text(0.5, 0.5, 'Throttle data not available',
                transform=ax.transAxes, ha='center', va='center',
                fontsize=10, color='grey')

    ax.set_ylabel('Throttle\nstate', fontsize=9)
    ax.grid(True, alpha=0.2, axis='x')


def _panel_power(ax, cpu_records: List[dict]):
    """Panel 3 – CPU package power (W) over time."""
    pwrs = [r.get('power_w') for r in cpu_records]
    times = _parse_times(cpu_records)
    pairs = [(t, v) for t, v in zip(times, pwrs) if v is not None]
    if not pairs:
        ax.text(0.5, 0.5, 'CPU power data not available',
                transform=ax.transAxes, ha='center', va='center',
                fontsize=10, color='grey')
    else:
        ts, vals = zip(*pairs)
        ax.fill_between(ts, vals, alpha=0.25, color='#3b82f6')
        ax.plot(ts, vals, color='#3b82f6', linewidth=1.3,
                label='CPU pkg power (W)')
        avg_w = sum(vals) / len(vals)
        ax.axhline(avg_w, color='#3b82f6', linestyle=':', linewidth=1.0,
                   alpha=0.7, label=f'avg {avg_w:.1f} W')
        ax.legend(loc='upper left', fontsize=8)
        ax.set_ylim(bottom=0)

    ax.set_ylabel('Power (W)', fontsize=9)
    ax.grid(True, alpha=0.25)


# ──────────────────────────────────────────────────────────────────────────────
# Main plot
# ──────────────────────────────────────────────────────────────────────────────

def plot_thermal(  # pylint: disable=too-many-locals
        cpu_records: List[dict],
        gpu_records: List[dict],
        session_label: str = '',
        output_file: Optional[str] = None,
        show: bool = False):
    """Render the thermal dashboard and optionally save / display it."""
    if not cpu_records and not gpu_records:
        print('  No thermal data to plot.', file=sys.stderr)
        return

    has_power = any(r.get('power_w') is not None for r in cpu_records)
    nrows = 3 if has_power else 2

    fig, axes = plt.subplots(nrows, 1,
                             figsize=(14, 3.5 * nrows),
                             sharex=False)
    if nrows == 1:
        axes = [axes]

    # ── Title ────────────────────────────────────────────────────────────────
    title = 'Thermal & Throttle Dashboard'
    if session_label:
        title += f'\n{session_label}'
    fig.suptitle(title, fontsize=13, fontweight='bold', y=0.998)
    fig.subplots_adjust(top=0.94, hspace=0.40)

    ax_iter = iter(axes)

    # Panel 1 – temperature
    ax1 = next(ax_iter)
    _panel_temperature(ax1, cpu_records, gpu_records)
    ax1.set_title('Temperature', fontsize=9, pad=3)
    _fmt_xaxis(ax1, _parse_times(cpu_records or gpu_records))

    # Panel 2 – throttle
    ax2 = next(ax_iter)
    _panel_throttle(ax2, cpu_records, gpu_records)
    ax2.set_title('Throttle State  (filled = throttling active)', fontsize=9, pad=3)
    _fmt_xaxis(ax2, _parse_times(cpu_records or gpu_records))

    # Panel 3 – power (conditional)
    if has_power:
        ax3 = next(ax_iter)
        _panel_power(ax3, cpu_records)
        ax3.set_title('CPU Package Power', fontsize=9, pad=3)
        _fmt_xaxis(ax3, _parse_times(cpu_records))

    axes[-1].set_xlabel('Time (HH:MM:SS)', fontsize=9)

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f'  Saved: {output_file}')
        if not show:
            plt.close(fig)
    if show:
        print('  Showing thermal dashboard – close window to continue.')
        plt.show()
        plt.close(fig)


def plot_temperature_only(
        cpu_records: List[dict],
        gpu_records: List[dict],
        session_label: str = '',
        output_file: Optional[str] = None,
        show: bool = False):
    """Render a standalone temperature-over-time chart and optionally save / display it."""
    if not cpu_records and not gpu_records:
        return
    fig, ax = plt.subplots(1, 1, figsize=(14, 4))
    title = 'CPU / GPU Temperature Over Time'
    if session_label:
        title += f'\n{session_label}'
    fig.suptitle(title, fontsize=12, fontweight='bold')
    _panel_temperature(ax, cpu_records, gpu_records)
    ax.set_title('Temperature', fontsize=9, pad=3)
    _fmt_xaxis(ax, _parse_times(cpu_records or gpu_records))
    ax.set_xlabel('Time (HH:MM:SS)', fontsize=9)
    fig.tight_layout()
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f'  Saved: {output_file}')
        if not show:
            plt.close(fig)
    if show:
        plt.show()
        plt.close(fig)


def plot_power_only(
        cpu_records: List[dict],
        session_label: str = '',
        output_file: Optional[str] = None,
        show: bool = False):
    """Render a standalone RAPL CPU package power chart and optionally save / display it."""
    has_power = any(r.get('power_w') is not None for r in cpu_records)
    if not cpu_records or not has_power:
        return
    fig, ax = plt.subplots(1, 1, figsize=(14, 4))
    title = 'CPU Package Power (RAPL) Over Time'
    if session_label:
        title += f'\n{session_label}'
    fig.suptitle(title, fontsize=12, fontweight='bold')
    _panel_power(ax, cpu_records)
    ax.set_title('CPU Package Power', fontsize=9, pad=3)
    _fmt_xaxis(ax, _parse_times(cpu_records))
    ax.set_xlabel('Time (HH:MM:SS)', fontsize=9)
    fig.tight_layout()
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f'  Saved: {output_file}')
        if not show:
            plt.close(fig)
    if show:
        plt.show()
        plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────────
# Session / file resolution helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_latest_session(sessions_root: Path) -> Optional[Path]:
    """Return the most recent session dir that contains a cpu_power.log."""
    if not sessions_root.exists():
        return None
    candidates = sorted(
        sessions_root.rglob('cpu_power.log'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0].parent if candidates else None


def _resolve_paths(args) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """
    Returns (cpu_log_path, gpu_log_path, vis_dir).

    Resolution order:
      1. Explicit positional log_file argument
      2. --session <directory path>
      3. Auto-detect latest session with cpu_power.log
    """
    sessions_root = Path(args.sessions_dir)
    vis_dir: Optional[Path] = None

    # ── Positional argument: could be a session dir or a direct log file ──
    if args.log_file:
        p = Path(args.log_file)
        if p.is_dir():
            # Treat as session directory
            cpu_log = p / 'cpu_power.log'
            gpu_log = p / 'gpu_usage.log'
            vis_dir = p / 'visualizations'
        else:
            cpu_log = p
            gpu_log = Path(args.gpu_log) if args.gpu_log else p.parent / 'gpu_usage.log'
        return cpu_log, gpu_log, vis_dir

    # ── --session ────────────────────────────────────────────────────────────
    if args.session:
        sess_dir = Path(args.session) if Path(args.session).is_dir() \
            else sessions_root / args.session
        vis_dir = sess_dir / 'visualizations'
        return sess_dir / 'cpu_power.log', sess_dir / 'gpu_usage.log', vis_dir

    # ── Auto-detect ──────────────────────────────────────────────────────────
    sess_dir = _find_latest_session(sessions_root)
    if sess_dir:
        vis_dir = sess_dir / 'visualizations'
        return sess_dir / 'cpu_power.log', sess_dir / 'gpu_usage.log', vis_dir

    return None, None, None


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():  # pylint: disable=too-many-branches,too-many-statements
    """Parse CLI arguments and render the thermal dashboard."""
    parser = argparse.ArgumentParser(
        description='Visualize CPU/GPU thermal and throttle data from a benchmark session',
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'log_file', nargs='?', default=None,
        help='Path to cpu_power.log or a session directory '
             '(auto-detected from latest session if omitted)',
    )
    parser.add_argument(
        '--session', '-s', default=None,
        help='Session name or path (e.g. monitoring_sessions/wandering/20260513_003015)',
    )
    parser.add_argument(
        '--gpu-log', default=None,
        help='Explicit path to gpu_usage.log (auto-found alongside cpu_power.log if omitted)',
    )
    parser.add_argument(
        '--sessions-dir', default='monitoring_sessions',
        help='Root directory for sessions (default: monitoring_sessions)',
    )
    parser.add_argument(
        '--output-dir', '-o', default=None,
        help='Directory to write the PNG file (default: session visualizations/)',
    )
    parser.add_argument(
        '--save', action='store_true',
        help='Save PNG to the session visualizations/ directory',
    )
    parser.add_argument(
        '--show', action='store_true',
        help='Open an interactive matplotlib window',
    )
    parser.add_argument(
        '--no-show', action='store_true',
        help='Never open a window (useful in headless CI)',
    )
    parser.add_argument(
        '--summary', action='store_true',
        help='Print text summary only, no plot',
    )
    args = parser.parse_args()

    # ── Resolve log paths ────────────────────────────────────────────────────
    cpu_log, gpu_log_path, vis_dir = _resolve_paths(args)

    if cpu_log is None:
        print('[Error] Could not locate cpu_power.log.\n'
              'Run a benchmark with:  make wandering-record\n'
              'or specify:  python src/visualize_thermal.py <session_dir>',
              file=sys.stderr)
        sys.exit(1)

    print(f'Loading CPU power log : {cpu_log}')
    cpu_records = load_cpu_power_log(cpu_log)

    if args.gpu_log:
        gpu_log_path = Path(args.gpu_log)
    print(f'Loading GPU usage log : {gpu_log_path}'
          + ('' if (gpu_log_path and gpu_log_path.exists()) else '  (not found, skipping)'))
    gpu_records = load_gpu_log(gpu_log_path)

    if not cpu_records and not gpu_records:
        print('[Error] No usable records found in either log.', file=sys.stderr)
        sys.exit(1)

    # ── Text summary ─────────────────────────────────────────────────────────
    print_summary(cpu_records, gpu_records)

    if args.summary:
        return

    # ── Output path ──────────────────────────────────────────────────────────
    show = args.show and not args.no_show

    out_dir: Optional[Path] = None
    if args.output_dir:
        out_dir = Path(args.output_dir)
    elif args.save and vis_dir:
        out_dir = vis_dir

    output_file: Optional[str] = None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(out_dir / 'thermal_throttle.png')

    # ── Session label for title ───────────────────────────────────────────────
    session_label = ''
    if cpu_log:
        session_label = str(cpu_log.parent)
        if cpu_records:
            t0 = cpu_records[0].get('ts', '')
            t1 = cpu_records[-1].get('ts', '')
            if t0 and t1:
                def _hms(iso):
                    return datetime.fromisoformat(iso).strftime('%H:%M:%S')
                session_label += f'   {_hms(t0)} – {_hms(t1)}  ({len(cpu_records)} samples)'

    # ── Plot ─────────────────────────────────────────────────────────────────
    print('Generating thermal dashboard...')
    plot_thermal(
        cpu_records,
        gpu_records,
        session_label=session_label,
        output_file=output_file,
        show=show,
    )

    # ── Separate temperature and power charts ─────────────────────────────────
    if out_dir:
        plot_temperature_only(
            cpu_records, gpu_records,
            session_label=session_label,
            output_file=str(out_dir / 'thermal_temperature.png'),
            show=False,
        )
        plot_power_only(
            cpu_records,
            session_label=session_label,
            output_file=str(out_dir / 'thermal_power.png'),
            show=False,
        )

    if not show and not out_dir:
        print('No --output-dir or --show specified; opening interactive window.')
        plt.show()

    print('Done.')


if __name__ == '__main__':
    main()
