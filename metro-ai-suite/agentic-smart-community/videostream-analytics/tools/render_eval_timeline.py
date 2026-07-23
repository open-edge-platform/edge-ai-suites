"""render_eval_timeline.py — ASCII timeline viz for prefilter eval results.

README
------
Eyeball-debug companion to `eval_prefilter_from_webhook.py`. Reads the same
events JSON + GT SRT (+ optional status JSON for accurate anchor) and prints
a side-by-side timeline of GT cues and motion events so you can see, at a
glance, *why* a particular cue was MISS or why an event was FP.

Why this exists
~~~~~~~~~~~~~~~
The fridge scenario in §24 came back with Recall 75% — a single MISS at
cue 1 (00:35-00:37) plus an FP at 00:32-00:34. Reading raw logs to figure
out the segment/cue overlap took ~15 minutes. With this view it would have
been one glance: cue 1's blue bar and event 1's green bar are clearly
adjacent but not overlapping — root cause is segment-edge misalignment,
not detection failure.

Output is pure ASCII, no matplotlib dependency.

Usage
-----
  # Use status JSON as anchor (most accurate; matches eval_prefilter_from_webhook --anchor-mode wallclock)
  python tools/render_eval_timeline.py \
    --srt ../videos/phase2/child-care/composed/child_safety_demo_groundtruth.srt \
    --events-json /tmp/child_events_92627.json \
    --status-json /tmp/child_status_92627.json \
    --source-id cam_child \
    --ss 40

  # First-event anchor (drifts; use only if no status dump available)
  python tools/render_eval_timeline.py \\
      --srt <gt.srt> --events-json events.json --anchor-mode first-event \\
      --source-id cam_child --ss 40

  # Adjust the canvas width (default 100 cols)
  python tools/render_eval_timeline.py ... --width 140

  # Filter out cues by label regex (mirrors eval_prefilter_from_webhook)
  python tools/render_eval_timeline.py ... --exclude-label-pattern '\\[EMPTY\\]'

Output
------
  Per-row: GT cues stacked above, then motion events stacked below, on a
  shared video-time axis. Symbols:
    [====]  GT cue (blue when SAFE, red when DANGEROUS, plain when other)
    {----}  motion event that overlaps ≥1 GT cue (HIT contribution)
    {**FP}  motion event that overlaps no GT cue (false positive)
  Each row has a video-time scale at the bottom.

Pure stdout, exit code 0 always.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.request import urlopen


# ---------------------------------------------------------------------------
# SRT + events loading (subset of eval_prefilter_from_webhook helpers)
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _ts_to_s(ts: str) -> float:
    m = _TS_RE.match(ts.strip())
    if not m:
        raise ValueError(f"bad ts: {ts!r}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000.0


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@dataclass
class GTCue:
    index: int
    start_s: float
    end_s: float
    label: str

    @property
    def kind(self) -> str:
        if "[DANGEROUS]" in self.label.upper():
            return "danger"
        if "[SAFE]" in self.label.upper():
            return "safe"
        if "[WAKEUP]" in self.label.upper():
            return "wakeup"
        if "[SLEEPING]" in self.label.upper():
            return "sleep"
        if "[TAKE]" in self.label.upper():
            return "take"
        return "other"


@dataclass
class MotionEvent:
    start_video_s: float
    end_video_s: float
    clip_path: str


def parse_srt(path: str, exclude_pattern: Optional[str]) -> List[GTCue]:
    text = Path(path).read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", text.strip())
    excl = re.compile(exclude_pattern, re.IGNORECASE) if exclude_pattern else None
    cues: List[GTCue] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0])
        except ValueError:
            continue
        tc = re.split(r"\s*-->\s*", lines[1])
        if len(tc) != 2:
            continue
        label = " ".join(lines[2:])
        if excl and excl.search(label):
            continue
        cues.append(GTCue(idx, _ts_to_s(tc[0]), _ts_to_s(tc[1]), label))
    return cues


def _normalize_event(e: dict) -> dict:
    """Phase 7: webhook envelope is nested. Flatten so downstream stays simple.

    Returns a dict with keys: event_type, source_id, start_time, end_time,
    clip_path — regardless of which schema the input file used.
    """
    if "payload" in e and isinstance(e["payload"], dict):
        p = e["payload"]
        return {
            "event_type": e.get("type"),
            "source_id": e.get("sourceId"),
            "start_time": p.get("start_time"),
            "end_time": p.get("end_time"),
            "clip_path": p.get("event_file_path") or p.get("recording_path", ""),
        }
    # Legacy flat schema fallthrough.
    return e


def load_events(events_json: str, source_id: Optional[str]) -> List[dict]:
    payload = json.loads(Path(events_json).read_text(encoding="utf-8"))
    raw = payload.get("events", payload) if isinstance(payload, dict) else payload
    out = []
    for raw_event in raw:
        e = _normalize_event(raw_event)
        if e.get("event_type") != "motion":
            continue
        if source_id and e.get("source_id") != source_id:
            continue
        out.append(e)
    out.sort(key=lambda e: e["start_time"])
    return out


def resolve_anchor(
    raw_events: List[dict],
    anchor_mode: str,
    status_json: Optional[str],
    analytics_url: Optional[str],
    source_id: Optional[str],
    anchor_wallclock: Optional[str],
) -> datetime:
    if anchor_mode == "stream-start":
        if status_json:
            data = json.loads(Path(status_json).read_text(encoding="utf-8"))
        else:
            if not (analytics_url and source_id):
                raise SystemExit(
                    "ERROR: --anchor-mode stream-start needs --status-json or both --analytics-url + --source-id"
                )
            url = f"{analytics_url.rstrip('/')}/sources/{source_id}"
            with urlopen(url, timeout=5) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8"))
        started = (data.get("health") or {}).get("start_time")
        if not started:
            raise SystemExit("ERROR: no health.start_time available")
        return _parse_iso(started)
    if anchor_mode == "first-event":
        if not raw_events:
            raise SystemExit("ERROR: no motion events to anchor on")
        return _parse_iso(raw_events[0]["start_time"])
    if anchor_mode == "wallclock":
        if not anchor_wallclock:
            raise SystemExit("ERROR: --anchor-wallclock required")
        return _parse_iso(anchor_wallclock)
    raise SystemExit(f"unknown anchor mode: {anchor_mode}")


def to_video_time(
    raw_events: List[dict], wall_t0: datetime, video_t0: float
) -> List[MotionEvent]:
    out = []
    for e in raw_events:
        s = _parse_iso(e["start_time"])
        en = _parse_iso(e["end_time"])
        out.append(MotionEvent(
            start_video_s=video_t0 + (s - wall_t0).total_seconds(),
            end_video_s=video_t0 + (en - wall_t0).total_seconds(),
            clip_path=e.get("clip_path", ""),
        ))
    return out


# ---------------------------------------------------------------------------
# Overlap classification (matches eval_prefilter_from_webhook semantics)
# ---------------------------------------------------------------------------

def _overlaps(a0, a1, b0, b1) -> bool:
    return min(a1, b1) > max(a0, b0)


def classify(cues: List[GTCue], events: List[MotionEvent], tolerance_s: float):
    """Return (cue_status, event_status). cue_status[i]='HIT'|'MISS'; event_status[j]='HIT'|'FP'."""
    cue_status: List[str] = []
    event_hit = [False] * len(events)
    for cue in cues:
        ws = cue.start_s - tolerance_s
        we = cue.end_s + tolerance_s
        any_hit = False
        for j, ev in enumerate(events):
            if _overlaps(ev.start_video_s, ev.end_video_s, ws, we):
                any_hit = True
                event_hit[j] = True
        cue_status.append("HIT" if any_hit else "MISS")
    event_status = ["HIT" if h else "FP" for h in event_hit]
    return cue_status, event_status


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _kind_glyph(kind: str) -> str:
    return {
        "danger": "D", "safe": "S", "wakeup": "W",
        "sleep": "Z", "take": "T", "other": "?",
    }.get(kind, "?")


def render(
    cues: List[GTCue],
    events: List[MotionEvent],
    cue_status: List[str],
    event_status: List[str],
    width: int,
) -> str:
    if not cues and not events:
        return "(no cues, no events)\n"

    t_min = 0.0
    t_max = 0.0
    if cues:
        t_max = max(t_max, max(c.end_s for c in cues))
    if events:
        t_max = max(t_max, max(e.end_video_s for e in events))
    if t_max <= t_min:
        t_max = t_min + 1.0

    # Reserve some left margin for labels.
    label_w = 5
    bar_w = width - label_w
    if bar_w < 20:
        bar_w = 20

    def col(t: float) -> int:
        c = int((t - t_min) / (t_max - t_min) * (bar_w - 1))
        return max(0, min(bar_w - 1, c))

    lines: list[str] = []

    # GT cues, one row per cue, vertically stacked
    if cues:
        lines.append(f"{'GT':>{label_w}} {'─' * bar_w}")
        for cue, status in zip(cues, cue_status):
            row = [' '] * bar_w
            c0 = col(cue.start_s)
            c1 = col(cue.end_s)
            if c1 == c0:
                c1 = min(bar_w - 1, c0 + 1)
            glyph = _kind_glyph(cue.kind)
            row[c0] = '['
            row[c1] = ']'
            for k in range(c0 + 1, c1):
                row[k] = '='
            row[c0] = '['
            row[c1] = ']'
            # Mark MISS clearly in the centre when there's room
            mid = (c0 + c1) // 2
            if status == "MISS" and c1 - c0 >= 4:
                row[mid] = 'X'
            elif c1 - c0 >= 3:
                row[mid] = glyph
            tag = f"#{cue.index}"
            lines.append(f"{tag:>{label_w}} {''.join(row)}  "
                         f"{cue.start_s:6.1f}-{cue.end_s:6.1f}s  "
                         f"{status:<4}  {cue.label[:60]}")

    # Motion events
    if events:
        lines.append(f"{'EV':>{label_w}} {'─' * bar_w}")
        for j, (ev, status) in enumerate(zip(events, event_status), 1):
            row = [' '] * bar_w
            c0 = col(ev.start_video_s)
            c1 = col(ev.end_video_s)
            if c1 == c0:
                c1 = min(bar_w - 1, c0 + 1)
            row[c0] = '{'
            row[c1] = '}'
            fill = '*' if status == "FP" else '-'
            for k in range(c0 + 1, c1):
                row[k] = fill
            row[c0] = '{'
            row[c1] = '}'
            tag = f"e{j}"
            lines.append(f"{tag:>{label_w}} {''.join(row)}  "
                         f"{ev.start_video_s:6.1f}-{ev.end_video_s:6.1f}s  "
                         f"{status:<4}  {Path(ev.clip_path).name}")

    # Time scale at the bottom (every 10% mark)
    scale = [' '] * bar_w
    label = [' '] * (bar_w + 12)
    for f in (0, 0.25, 0.5, 0.75, 1.0):
        c = int(f * (bar_w - 1))
        scale[c] = '|'
        t = t_min + f * (t_max - t_min)
        s = f"{int(t // 60):02d}:{int(t % 60):02d}"
        for k, ch in enumerate(s):
            pos = c + k
            if 0 <= pos < len(label):
                label[pos] = ch
    lines.append(f"{'':>{label_w}} {''.join(scale)}")
    lines.append(f"{'':>{label_w}} {''.join(label)}")

    return "\n".join(lines) + "\n"


def summary_block(cue_status: List[str], event_status: List[str]) -> str:
    n_cue = len(cue_status)
    n_hit = sum(1 for s in cue_status if s == "HIT")
    n_miss = n_cue - n_hit
    n_ev = len(event_status)
    n_ev_hit = sum(1 for s in event_status if s == "HIT")
    n_fp = n_ev - n_ev_hit
    recall = (n_hit / n_cue * 100) if n_cue else 0.0
    precision = (n_ev_hit / n_ev * 100) if n_ev else 0.0
    return (
        "─" * 56 + "\n"
        f"  GT cues : {n_cue:>3}  ({n_hit} HIT, {n_miss} MISS)\n"
        f"  Events  : {n_ev:>3}  ({n_ev_hit} HIT, {n_fp} FP)\n"
        f"  Recall  : {recall:5.1f}%   Precision: {precision:5.1f}%\n"
        + "─" * 56 + "\n"
        + "Legend: [====]=GT cue  X=MISS  D=danger S=safe W=wakeup Z=sleep T=take\n"
        + "        {----}=event HIT  {****}=event FP\n"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="ASCII timeline visualization for prefilter eval results."
    )
    ap.add_argument("--srt", required=True)
    ap.add_argument("--events-json", required=True)
    ap.add_argument("--source-id")
    ap.add_argument("--status-json", help="Status dump for accurate stream-start anchor")
    ap.add_argument(
        "--analytics-url", default="http://localhost:8999",
        help="Used by --anchor-mode stream-start when --status-json is absent",
    )
    ap.add_argument(
        "--anchor-mode",
        choices=["stream-start", "first-event", "wallclock"],
        default="stream-start",
    )
    ap.add_argument("--anchor-wallclock", help="ISO timestamp for --anchor-mode wallclock")
    ap.add_argument("--ss", type=float, default=0.0,
                    help="Video-time anchor (matches ffmpeg `-ss N`)")
    ap.add_argument("--tolerance", type=float, default=0.0,
                    help="Seconds to expand each GT window on both sides")
    ap.add_argument("--exclude-label-pattern",
                    help="Regex; matching cues are dropped (e.g. '\\[EMPTY\\]')")
    ap.add_argument("--width", type=int, default=100,
                    help="Total terminal width for the timeline (default 100)")
    args = ap.parse_args()

    cues = parse_srt(args.srt, args.exclude_label_pattern)
    if not cues:
        print("ERROR: no cues parsed", file=sys.stderr); sys.exit(1)

    raw_events = load_events(args.events_json, args.source_id)
    if not raw_events:
        print("ERROR: no motion events found", file=sys.stderr); sys.exit(1)

    wall_t0 = resolve_anchor(
        raw_events, args.anchor_mode, args.status_json,
        args.analytics_url, args.source_id, args.anchor_wallclock,
    )
    events = to_video_time(raw_events, wall_t0, args.ss)

    cue_status, event_status = classify(cues, events, args.tolerance)
    print(render(cues, events, cue_status, event_status, args.width))
    print(summary_block(cue_status, event_status))
    print(f"Anchor : wall_t0={wall_t0.isoformat()}  video_t0={args.ss}s  "
          f"tolerance=±{args.tolerance}s")


if __name__ == "__main__":
    main()
