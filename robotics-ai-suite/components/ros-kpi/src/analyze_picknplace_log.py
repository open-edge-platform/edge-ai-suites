#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Parse picknplace_launch.log and populate the session kpi.json with real KPIs.

The picknplace scenario involves three cooperating state machines:
  ARM1 (picks cubes from conveyor) → AMR (transports) → ARM2 (places on shelf)

From the launch log, this script extracts per-phase timestamps to derive:

  startup_s           : time from launch to ARM1 MoveIt-ready
  grasp_count         : number of successful ARM1 grasps in the run
  grasp_duration_s    : ARM1 gripper-close → GRASP SUCCESS  (per attempt)
  approach_duration_s : ARM1 cube-detected → cube-stopped   (per attempt)
  detect_to_grasp_s   : ARM1 cube-detected → GRASP SUCCESS  (full pick cycle)
  cycle_time_s        : GRASP SUCCESS[n] → GRASP SUCCESS[n+1]  (if ≥2 cycles)
  total_elapsed_s     : first → last timestamp in the log
  demo_complete       : True when "ARM2 at standby. Demo complete." is seen

ARM1 pick-cycle state sequence:
  WAIT (Locked onto cube) → APPROACH (PRE-POSITIONING) → APPROACH (Cube stopped)
  → GRASP (ATTEMPT 1) → GRASP (✓ GRASP SUCCESS) → PLACE (Lifting cube HIGH)

ARM2/AMR events (where visible in the log):
  Placed successfully  → ARM2 placed cube on shelf
  ARM2 at standby. Demo complete. → full cycle done
"""

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean, pstdev
from textwrap import dedent as textwrap_dedent
from typing import Optional


# ── Log-parsing patterns ───────────────────────────────────────────────────────

# ROS 2 nanosecond timestamp embedded in log lines: [<sec>.<nsec>]
_TS = r'\[(\d+\.\d+)\]'

# ARM1 MoveIt ready — marks end of startup
_RE_ARM1_READY = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*MoveIt planning service is ready'
)

# ARM1 locked onto a cube on the conveyor
_RE_CUBE_DETECTED = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*\[STATE: WAIT\] Locked onto (\w+) at Y=([\d.]+)m'
)

# ARM1 begins moving to the pre-grasp intercept position
_RE_APPROACH_START = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*\[STATE: APPROACH\].*PRE-POSITIONING FOR GRASP'
)

# ARM1 cube has stopped in the grasp window
_RE_CUBE_STOPPED = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*\[STATE: APPROACH\] Cube stopped at world'
)

# ARM1 first grasp attempt (gripper starts closing)
_RE_GRASP_ATTEMPT = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*\[STATE: GRASP\].*ATTEMPT (\d+)/3'
)

# ARM1 grasp confirmed successful
_RE_GRASP_SUCCESS = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*\[STATE: GRASP\].*GRASP SUCCESS'
)

# ARM1 approach timed out (cube was missed)
_RE_APPROACH_TIMEOUT = re.compile(
    rf'arm1_controller[^\]]*\]\s*\[WARN\]\s*{_TS}.*\[STATE: APPROACH\] Timeout waiting'
)

# ARM2 successfully placed cube on shelf
_RE_PLACED = re.compile(
    rf'arm2_controller[^\]]*\]\s*\[INFO\]\s*{_TS}.*[Pp]laced successfully'
)

# Full demo cycle complete
_RE_DEMO_COMPLETE = re.compile(
    rf'{_TS}.*ARM2 at standby\. Demo complete\.'
)

# Any timestamped ROS line (for first/last bookmarks)
_RE_ANY_TS = re.compile(r'\[(INFO|WARN|ERROR)\]\s+\[(\d+\.\d+)\]')


# ── Data structures ────────────────────────────────────────────────────────────

class PickAttempt:
    """Records timestamps for one ARM1 pick-cycle attempt."""

    def __init__(self, cube_id: str, t_detected: float):
        self.cube_id = cube_id
        self.t_detected: float = t_detected
        self.t_approach: Optional[float] = None    # PRE-POSITIONING
        self.t_cube_stopped: Optional[float] = None
        self.t_grasp_attempt: Optional[float] = None
        self.attempt_num: int = 1
        self.t_grasp_success: Optional[float] = None
        self.t_timeout: Optional[float] = None
        self.success: bool = False

    @property
    def approach_duration_s(self) -> Optional[float]:
        """Cube detected → cube stopped in grasp window."""
        if self.t_detected and self.t_cube_stopped:
            return self.t_cube_stopped - self.t_detected
        return None

    @property
    def grasp_duration_s(self) -> Optional[float]:
        """Gripper-close command → GRASP SUCCESS."""
        if self.t_grasp_attempt and self.t_grasp_success:
            return self.t_grasp_success - self.t_grasp_attempt
        return None

    @property
    def detect_to_grasp_s(self) -> Optional[float]:
        """Cube detected → GRASP SUCCESS (full ARM1 pick cycle)."""
        if self.t_detected and self.t_grasp_success:
            return self.t_grasp_success - self.t_detected
        return None


# ── Log parsing ────────────────────────────────────────────────────────────────

def parse_log(log_path: Path) -> dict:
    """
    Scan picknplace_launch.log and return a structured result dict.

    Returns
    -------
    dict with keys:
      first_t           : float   — first log timestamp
      last_t            : float   — last log timestamp
      arm1_ready_t      : float | None
      startup_s         : float | None
      attempts          : list[PickAttempt]
      successful_grasps : list[PickAttempt]
      missed_attempts   : list[PickAttempt]
      placements        : list[float]   — timestamps of ARM2 "Placed successfully"
      demo_complete_t   : float | None
    """
    text = log_path.read_text(errors='replace')
    lines = text.splitlines()

    first_t: Optional[float] = None
    last_t: Optional[float] = None
    arm1_ready_t: Optional[float] = None
    demo_complete_t: Optional[float] = None
    placements: list[float] = []

    attempts: list[PickAttempt] = []
    current: Optional[PickAttempt] = None  # the in-progress attempt

    for line in lines:
        # Track first/last timestamp
        m = _RE_ANY_TS.search(line)
        if m:
            t = float(m.group(2))
            if first_t is None:
                first_t = t
            last_t = t

        # ARM1 ready
        m = _RE_ARM1_READY.search(line)
        if m and arm1_ready_t is None:
            arm1_ready_t = float(m.group(1))
            continue

        # Cube detected → start a new attempt
        m = _RE_CUBE_DETECTED.search(line)
        if m:
            # If previous attempt hasn't closed yet, keep it (it may still succeed
            # if the arm retries), but start tracking the new detection separately.
            # In practice ARM1 only tracks one cube at a time.
            if current is not None and not current.success and current.t_timeout is None:
                # Overwritten by a new detection while approach was in progress;
                # treat old one as abandoned
                attempts.append(current)
            current = PickAttempt(cube_id=m.group(2), t_detected=float(m.group(1)))
            continue

        if current is None:
            # Ignore events before first cube detection
            continue

        # Approach start
        m = _RE_APPROACH_START.search(line)
        if m and current.t_approach is None:
            current.t_approach = float(m.group(1))
            continue

        # Cube stopped
        m = _RE_CUBE_STOPPED.search(line)
        if m and current.t_cube_stopped is None:
            current.t_cube_stopped = float(m.group(1))
            continue

        # Grasp attempt (first one per cycle)
        m = _RE_GRASP_ATTEMPT.search(line)
        if m and current.t_grasp_attempt is None:
            current.t_grasp_attempt = float(m.group(1))
            current.attempt_num = int(m.group(2))
            continue

        # Grasp success
        m = _RE_GRASP_SUCCESS.search(line)
        if m:
            current.t_grasp_success = float(m.group(1))
            current.success = True
            attempts.append(current)
            current = None
            continue

        # Approach timeout (missed cube)
        m = _RE_APPROACH_TIMEOUT.search(line)
        if m:
            current.t_timeout = float(m.group(1))
            attempts.append(current)
            current = None
            continue

        # ARM2 placement
        m = _RE_PLACED.search(line)
        if m:
            placements.append(float(m.group(1)))
            continue

        # Demo complete
        m = _RE_DEMO_COMPLETE.search(line)
        if m and demo_complete_t is None:
            demo_complete_t = float(m.group(1))

    # Close any open attempt at end-of-log (run was killed mid-cycle)
    if current is not None:
        attempts.append(current)

    successful_grasps = [a for a in attempts if a.success]
    missed_attempts = [a for a in attempts if a.t_timeout is not None]

    startup_s: Optional[float] = None
    if first_t is not None and arm1_ready_t is not None:
        startup_s = arm1_ready_t - first_t

    return {
        'first_t':           first_t,
        'last_t':            last_t,
        'arm1_ready_t':      arm1_ready_t,
        'startup_s':         startup_s,
        'attempts':          attempts,
        'successful_grasps': successful_grasps,
        'missed_attempts':   missed_attempts,
        'placements':        placements,
        'demo_complete_t':   demo_complete_t,
    }


# ── KPI derivation ─────────────────────────────────────────────────────────────

def _stat(values: list[float]) -> dict:
    """Return mean/min/max/stdev for a list of floats (rounded to 3 dp)."""
    if not values:
        return {'mean': None, 'min': None, 'max': None, 'stdev': None, 'n': 0}
    return {
        'mean':  round(mean(values), 3),
        'min':   round(min(values), 3),
        'max':   round(max(values), 3),
        'stdev': round(pstdev(values), 3) if len(values) > 1 else 0.0,
        'n':     len(values),
    }


def _derive_kpis(parsed: dict) -> dict:
    """
    Derive KPI values from the parsed log data.

    Latency / timing KPIs are ARM1-centric (the ARM1 pick cycle is the
    innermost loop and the primary performance bottleneck).

      approach_duration_s  : cube detected → cube stopped in grasp window
      grasp_duration_s     : first gripper-close command → GRASP SUCCESS
      detect_to_grasp_s    : cube detected → GRASP SUCCESS  (full pick cycle)
      cycle_time_s         : GRASP SUCCESS[n] → GRASP SUCCESS[n+1]

    throughput_hz is expressed as successful grasps per second over the
    elapsed window between first and last GRASP SUCCESS (excludes startup).
    """
    grasps = parsed['successful_grasps']

    approach_vals = [a.approach_duration_s for a in grasps if a.approach_duration_s is not None]
    grasp_dur_vals = [a.grasp_duration_s for a in grasps if a.grasp_duration_s is not None]
    d2g_vals = [a.detect_to_grasp_s for a in grasps if a.detect_to_grasp_s is not None]

    # Cycle time: gap between consecutive grasp successes
    cycle_times: list[float] = []
    ts_success = [a.t_grasp_success for a in grasps if a.t_grasp_success is not None]
    for i in range(1, len(ts_success)):
        cycle_times.append(ts_success[i] - ts_success[i - 1])

    # Throughput: grasps/s between first and last success
    throughput_hz: Optional[float] = None
    if len(ts_success) >= 2:
        span = ts_success[-1] - ts_success[0]
        throughput_hz = round((len(ts_success) - 1) / span, 4) if span > 0 else None

    total_elapsed_s: Optional[float] = None
    if parsed['first_t'] is not None and parsed['last_t'] is not None:
        total_elapsed_s = round(parsed['last_t'] - parsed['first_t'], 3)

    return {
        'grasp_count':          len(grasps),
        'placement_count':      len(parsed['placements']),
        'missed_count':         len(parsed['missed_attempts']),
        'demo_complete':        parsed['demo_complete_t'] is not None,
        'startup_s':            round(parsed['startup_s'], 3) if parsed['startup_s'] is not None else None,
        'total_elapsed_s':      total_elapsed_s,
        'throughput_hz':        throughput_hz,
        # Per-attempt stats
        'approach_duration_s':  _stat(approach_vals),
        'grasp_duration_s':     _stat(grasp_dur_vals),
        'detect_to_grasp_s':    _stat(d2g_vals),
        'cycle_time_s':         _stat(cycle_times),
        # Derived from grasp_duration for kpi.json Level-1 compatibility
        'mean_latency_ms':      round(mean(grasp_dur_vals) * 1000, 3) if grasp_dur_vals else None,
        'mean_cycle_ms':        round(mean(cycle_times) * 1000, 3) if cycle_times else None,
    }


# ── kpi.json patching ──────────────────────────────────────────────────────────

def _patch_kpi(kpi_path: Path, parsed: dict, kpis: dict) -> None:
    """Load kpi.json, populate picknplace-specific fields, and write back."""
    kpi = json.loads(kpi_path.read_text())

    # Level-1 fields: use grasp rate as throughput, grasp duration as latency
    kpi['throughput_hz']   = kpis['throughput_hz']
    kpi['mean_latency_ms'] = kpis['mean_latency_ms']

    # Jitter fields: express cycle-time variability as jitter
    cst = kpis['cycle_time_s']
    if cst['n'] > 0 and cst['mean'] is not None:
        kpi['mean_jitter_ms']  = round(cst['stdev'] * 1000, 3)
        kpi['max_jitter_ms']   = round((cst['max'] - cst['mean']) * 1000, 3)
        kpi['min_jitter_ms']   = 0.0
        kpi['jitter_stdev_ms'] = round(cst['stdev'] * 1000, 3)

    # per_node: ARM1 pick-cycle entry
    gst = kpis['grasp_duration_s']
    kpi.setdefault('per_node', {})['/arm1/ARM1Controller'] = {
        'throughput_hz':    kpis['throughput_hz'],
        'mean_latency_ms':  kpis['mean_latency_ms'],
        'mean_jitter_ms':   round(gst['stdev'] * 1000, 3) if gst['n'] > 1 else 0.0,
        'max_jitter_ms':    round((gst['max'] - gst['mean']) * 1000, 3) if gst['n'] > 1 else 0.0,
        'num_samples':      kpis['grasp_count'],
        'primary_input':    '/arm1/cube_pose',
        'primary_output':   '/arm1/gripper_state',
        'pipeline_stage':   'Manipulation',
    }

    kpi_path.write_text(json.dumps(kpi, indent=2))
    print(f'  kpi.json patched   → {kpi_path}')


# ── Sidecar JSON ───────────────────────────────────────────────────────────────

def _write_cycles(session_dir: Path, parsed: dict, kpis: dict) -> None:
    """Write per-attempt timeline data to picknplace_cycles.json."""

    def _attempt_dict(a: PickAttempt) -> dict:
        return {
            'cube_id':           a.cube_id,
            't_detected':        a.t_detected,
            't_approach':        a.t_approach,
            't_cube_stopped':    a.t_cube_stopped,
            't_grasp_attempt':   a.t_grasp_attempt,
            'attempt_num':       a.attempt_num,
            't_grasp_success':   a.t_grasp_success,
            't_timeout':         a.t_timeout,
            'success':           a.success,
            'approach_duration_s': a.approach_duration_s,
            'grasp_duration_s':    a.grasp_duration_s,
            'detect_to_grasp_s':   a.detect_to_grasp_s,
        }

    out = {
        'startup_s':          kpis['startup_s'],
        'total_elapsed_s':    kpis['total_elapsed_s'],
        'grasp_count':        kpis['grasp_count'],
        'placement_count':    kpis['placement_count'],
        'missed_count':       kpis['missed_count'],
        'demo_complete':      kpis['demo_complete'],
        'throughput_hz':      kpis['throughput_hz'],
        'approach_duration_s': kpis['approach_duration_s'],
        'grasp_duration_s':    kpis['grasp_duration_s'],
        'detect_to_grasp_s':   kpis['detect_to_grasp_s'],
        'cycle_time_s':        kpis['cycle_time_s'],
        'attempts':           [_attempt_dict(a) for a in parsed['attempts']],
    }
    out_path = session_dir / 'picknplace_cycles.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'  cycles written     → {out_path}')


# ── CLI summary ────────────────────────────────────────────────────────────────

def _fmt(val, unit='s', decimals=2) -> str:
    if val is None:
        return '     n/a'
    return f'{val:>8.{decimals}f} {unit}'


def _print_summary(parsed: dict, kpis: dict) -> None:
    """Print a human-readable summary to stdout."""
    grasps = parsed['successful_grasps']
    missed = parsed['missed_attempts']
    complete = '✓ YES' if kpis['demo_complete'] else '✗ NO (run killed / timed out)'

    print('')
    print('  ┌─ Pick-and-Place Task Performance ───────────────────────┐')
    print(f'  │  Demo complete    : {complete}')
    print(f'  │  Successful grasps: {kpis["grasp_count"]:>3}   '
          f'   Missed: {kpis["missed_count"]:>2}   '
          f'   Placements: {kpis["placement_count"]:>2}')
    print(f'  │  Startup time     : {_fmt(kpis["startup_s"])}')
    print(f'  │  Total elapsed    : {_fmt(kpis["total_elapsed_s"])}')
    if kpis['throughput_hz'] is not None:
        print(f'  │  Grasp rate       : {kpis["throughput_hz"]:.4f} Hz '
              f'(between 1st and last success)')
    print('  ├─ ARM1 Phase Durations (mean / min / max) ───────────────┤')

    def _row(label: str, stat: dict, unit: str = 's') -> None:
        if stat['n'] == 0:
            print(f'  │  {label:<26} n/a')
            return
        print(
            f'  │  {label:<26} '
            f'mean={stat["mean"]:.3f}{unit}  '
            f'min={stat["min"]:.3f}  '
            f'max={stat["max"]:.3f}  '
            f'(n={stat["n"]})'
        )

    _row('Approach duration', kpis['approach_duration_s'])
    _row('Grasp duration', kpis['grasp_duration_s'])
    _row('Detect → grasp', kpis['detect_to_grasp_s'])
    _row('Cycle time', kpis['cycle_time_s'])

    if grasps:
        print('  ├─ Per-Grasp Detail ────────────────────────────────────────┤')
        for i, a in enumerate(grasps, 1):
            g = f'{a.grasp_duration_s:.2f}s' if a.grasp_duration_s is not None else '?'
            d = f'{a.detect_to_grasp_s:.2f}s' if a.detect_to_grasp_s is not None else '?'
            print(f'  │  Grasp {i:>2} ({a.cube_id:<8}) '
                  f'attempt={a.attempt_num}  grasp={g}  total={d}')
    if missed:
        print('  ├─ Missed Attempts ─────────────────────────────────────────┤')
        for a in missed:
            print(f'  │  missed {a.cube_id}  (approach timed out)')

    print('  └───────────────────────────────────────────────────────────┘')
    print('')


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Parse picknplace_launch.log and patch session kpi.json.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap_dedent('''\
        Examples:
          # Auto-discover log and kpi.json in session dir:
          uv run python src/analyze_picknplace_log.py \\
            --session monitoring_sessions/picknplace/20260529_134637

          # Explicit paths:
          uv run python src/analyze_picknplace_log.py \\
            --log monitoring_sessions/picknplace/20260529_134637/picknplace_launch.log \\
            --kpi monitoring_sessions/picknplace/20260529_134637/kpi.json

          # Parse only, do not modify kpi.json:
          uv run python src/analyze_picknplace_log.py \\
            --session monitoring_sessions/picknplace/20260529_134637 --no-patch
        '''),
    )
    parser.add_argument(
        '--session', '-s',
        default=None,
        metavar='DIR',
        help='Session directory — auto-discovers picknplace_launch.log and kpi.json.',
    )
    parser.add_argument(
        '--log',
        default=None,
        metavar='FILE',
        help='Path to picknplace_launch.log (overrides --session log discovery).',
    )
    parser.add_argument(
        '--kpi',
        default=None,
        metavar='FILE',
        help='Path to kpi.json to patch (overrides --session kpi discovery).',
    )
    parser.add_argument(
        '--no-patch',
        action='store_true',
        help='Parse and print summary only; do not modify kpi.json.',
    )
    args = parser.parse_args()

    # Resolve paths
    if args.session:
        session_dir = Path(args.session).resolve()
        log_path = Path(args.log).resolve() if args.log else session_dir / 'picknplace_launch.log'
        kpi_path = Path(args.kpi).resolve() if args.kpi else session_dir / 'kpi.json'
    elif args.log:
        log_path = Path(args.log).resolve()
        session_dir = log_path.parent
        kpi_path = Path(args.kpi).resolve() if args.kpi else session_dir / 'kpi.json'
    else:
        parser.error('Provide --session DIR or --log FILE.')
        return 1

    if not log_path.exists():
        print(f'ERROR: log file not found: {log_path}', file=sys.stderr)
        return 1

    parsed = parse_log(log_path)

    if parsed['first_t'] is None:
        print('ERROR: No timestamped log lines found — is this a picknplace launch log?',
              file=sys.stderr)
        return 1

    if not parsed['attempts']:
        print('WARNING: No ARM1 pick attempts detected in the log.', file=sys.stderr)
        print('         The run may have been killed before ARM1 initialised.')

    kpis = _derive_kpis(parsed)
    _print_summary(parsed, kpis)

    if args.no_patch:
        return 0

    _write_cycles(session_dir, parsed, kpis)

    if kpi_path.exists():
        _patch_kpi(kpi_path, parsed, kpis)
    else:
        print(f'  ⚠ kpi.json not found at {kpi_path} — skipping patch', file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
