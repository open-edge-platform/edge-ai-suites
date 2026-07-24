"""eval_prefilter_from_webhook.py — Prefilter recall/precision evaluator (webhook-source variant)

README
------
Evaluates the motion + YOLO prefilter pipeline of `videostream-analytics` against
a ground-truth SRT file, by reading motion events from the integration test's
mock webhook server (tests/integration/mock_webhook_server.py) instead of from a
phase-2 prototype `pipeline.db`.

Background
~~~~~~~~~~
The phase-2 prototype shipped two evaluators in
`phase2-prototype-demo/tools/eval_prefilter_coverage.py` and
`eval_alert_accuracy.py`. Both read `pipeline.db.tasks`, which only existed in
the prototype's in-process pipeline. In the new architecture, this microservice
posts events to an external webhook (e.g. the MCP Server `/events` endpoint)
and never persists tasks locally — the prefilter does not even emit a
`prefilter_skip` event upstream; it just stays silent. So this script only
reports the metrics that are observable from outside:

  Per GT cue
    HIT     – ≥1 motion webhook event overlaps the GT window
    MISS    – no overlapping motion event (prefilter+motion together missed it)

  Global
    Recall    – #HIT / total_gt
    Precision – fraction of motion events that overlap ≥1 GT window
                (false positives = motion event with NO GT overlap)

The metrics that need DB-level visibility (`prefilter_skip` count, skip_rate,
PARTIAL outcome) are NOT computable from webhook output; the original
`eval_prefilter_coverage.py` is still the right tool for that and runs on the
prototype's `pipeline.db`.

Webhook source
~~~~~~~~~~~~~~
There are two ways to feed motion events in:

  1. Live: query a running mock webhook server (default
     http://localhost:9999/recorded_events/motion) — the same one
     `scripts/test-videostream-analytics.sh` already starts.

  2. File: pass `--events-json /path/to/events.json` containing the
     `{"events": [...], "count": N}` shape returned by that endpoint.

Time alignment
~~~~~~~~~~~~~~
Webhook payloads carry wall-clock ISO timestamps (`start_time` / `end_time`),
but a GT SRT cue is in *video time* (seconds since stream start). We need an
anchor: when did wall-clock T0 correspond to video second V0?

  --anchor-mode stream-start (recommended; service must be running)
      Query GET /sources/{id}/status and use `health.start_time` as wall-clock
      T0 — the moment the RTSP stream actually opened. Video T0 is --ss
      (the ffmpeg `-ss N` seek used to push the test video). This is the only
      mode that doesn't drift when motion events start late in the video.
      Requires --source-id and --analytics-url.

  --anchor-mode first-event (default; works offline)
      Use the earliest motion event's start_time as wall-clock T0, and assume
      it maps to --ss seconds in the GT video. This DRIFTS by however long
      it took for the first real motion to appear (typically 5-15s after the
      stream opened) — usable when the GT cue 1 is right at the video start.

  --anchor-mode wallclock
      Pass --anchor-wallclock <ISO> + --ss <float> explicitly. Escape hatch
      for replaying old runs where neither the service nor a fresh dump is
      available.

Usage
-----
  # Recommended: stream-start anchor (service must still be up).
  # --ss matches the ffmpeg `-ss N` seek used to push the demo video.
  python tools/eval_prefilter_from_webhook.py \\
      --srt ../videos/phase2/child-care/composed/child_safety_demo_groundtruth.srt \\
      --source-id cam_child --anchor-mode stream-start --ss 40

  # Offline: against an exported events dump. Anchor drifts; only OK if
  # GT cue 1 starts at the very beginning of the video.
  curl -s http://localhost:9999/recorded_events > events.json
  python tools/eval_prefilter_from_webhook.py --srt <gt.srt> \\
      --events-json events.json --source-id cam_child --ss 40

  # Loosen overlap matching by ±2s on each side:
  python tools/eval_prefilter_from_webhook.py --srt <gt.srt> --tolerance 2.0

Exit code
---------
  0 always (this is a reporting tool, not a gate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.request import urlopen


# ---------------------------------------------------------------------------
# SRT parsing (same shape as phase2 eval_prefilter_coverage.py)
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _ts_to_s(ts: str) -> float:
    m = _TS_RE.match(ts.strip())
    if not m:
        raise ValueError(f"Cannot parse timestamp: {ts!r}")
    h, mn, s, ms = int(m[1]), int(m[2]), int(m[3]), int(m[4])
    return h * 3600 + mn * 60 + s + ms / 1000.0


@dataclass
class GTCue:
    index: int
    start_s: float
    end_s: float
    label: str


def parse_srt(path: str, exclude_pattern: Optional[str] = None) -> List[GTCue]:
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
        tc_parts = re.split(r"\s*-->\s*", lines[1])
        if len(tc_parts) != 2:
            continue
        label = " ".join(lines[2:])
        if excl and excl.search(label):
            continue
        cues.append(GTCue(
            index=idx,
            start_s=_ts_to_s(tc_parts[0]),
            end_s=_ts_to_s(tc_parts[1]),
            label=label,
        ))
    return cues


# ---------------------------------------------------------------------------
# Webhook event loading
# ---------------------------------------------------------------------------

@dataclass
class MotionEvent:
    source_id: str
    start_wall: datetime
    end_wall: datetime
    duration_s: float
    clip_path: str
    # Filled in once we have an anchor:
    start_video_s: Optional[float] = None
    end_video_s: Optional[float] = None


def _parse_iso(ts: str) -> datetime:
    # The webhook client uses datetime.now().isoformat() which has no tz info.
    # Accept both +00:00 form and naive form.
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Cannot parse ISO timestamp: {ts!r}") from e


def _load_motion_events_from_payload(payload: dict, source_id: Optional[str]) -> List[MotionEvent]:
    raw = payload.get("events", payload) if isinstance(payload, dict) else payload
    events = []
    for ev in raw:
        # Phase 7: nested envelope {sourceId, type, timestamp, payload}.
        # Tolerate legacy flat schema for backwards compatibility.
        nested = isinstance(ev.get("payload"), dict)
        ev_type = ev.get("type") if nested else ev.get("event_type")
        if ev_type != "motion":
            continue
        sid = ev.get("sourceId") if nested else ev.get("source_id")
        if source_id and sid != source_id:
            continue
        body = ev["payload"] if nested else ev
        clip = body.get("event_file_path") or body.get("clip_path", "")
        events.append(MotionEvent(
            source_id=sid or "?",
            start_wall=_parse_iso(body["start_time"]),
            end_wall=_parse_iso(body["end_time"]),
            duration_s=float(body.get("duration_seconds", 0.0)),
            clip_path=clip,
        ))
    events.sort(key=lambda e: e.start_wall)
    return events


def load_motion_events(
    events_url: Optional[str],
    events_json: Optional[str],
    source_id: Optional[str],
) -> List[MotionEvent]:
    if events_json:
        payload = json.loads(Path(events_json).read_text(encoding="utf-8"))
    else:
        with urlopen(events_url, timeout=5) as resp:  # nosec B310 (local URL)
            payload = json.loads(resp.read().decode("utf-8"))
    return _load_motion_events_from_payload(payload, source_id)


# ---------------------------------------------------------------------------
# Time anchor: wall-clock ↔ video-time
# ---------------------------------------------------------------------------

def fetch_stream_start_time(analytics_url: str, source_id: str) -> datetime:
    """GET /sources/{id} → health.start_time (wall-clock the RTSP opened)."""
    url = f"{analytics_url.rstrip('/')}/sources/{source_id}"
    try:
        with urlopen(url, timeout=5) as resp:  # nosec B310 (local URL)
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise SystemExit(
            f"ERROR: cannot reach analytics service at {url}: {e}\n"
            f"  --anchor-mode stream-start needs the service still running.\n"
            f"  Use --anchor-mode first-event for offline replay."
        ) from e
    health = data.get("health") or {}
    started = health.get("start_time")
    if not started:
        raise SystemExit(
            f"ERROR: /sources/{source_id} has no health.start_time. "
            f"Has the source actually opened the stream yet?"
        )
    return _parse_iso(started)


def apply_anchor(
    events: List[MotionEvent],
    anchor_mode: str,
    anchor_wallclock: Optional[str],
    ss: float,
    analytics_url: Optional[str],
    source_id: Optional[str],
) -> Tuple[datetime, float]:
    """Mutates events to set start_video_s/end_video_s. Returns (wall_t0, video_t0)."""
    if not events:
        raise SystemExit("ERROR: no motion events to evaluate")

    if anchor_mode == "stream-start":
        if not source_id:
            raise SystemExit("ERROR: --anchor-mode stream-start requires --source-id")
        if not analytics_url:
            raise SystemExit("ERROR: --anchor-mode stream-start requires --analytics-url")
        wall_t0 = fetch_stream_start_time(analytics_url, source_id)
        video_t0 = ss
    elif anchor_mode == "first-event":
        wall_t0 = events[0].start_wall
        video_t0 = ss
    elif anchor_mode == "wallclock":
        if not anchor_wallclock:
            raise SystemExit("ERROR: --anchor-mode wallclock requires --anchor-wallclock")
        wall_t0 = _parse_iso(anchor_wallclock)
        video_t0 = ss
    else:
        raise SystemExit(f"ERROR: unknown anchor mode: {anchor_mode}")

    for e in events:
        e.start_video_s = video_t0 + (e.start_wall - wall_t0).total_seconds()
        e.end_video_s = video_t0 + (e.end_wall - wall_t0).total_seconds()
    return wall_t0, video_t0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _overlap_s(a_start, a_end, b_start, b_end) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


@dataclass
class CueResult:
    cue: GTCue
    matched: List[MotionEvent] = field(default_factory=list)

    @property
    def status_label(self) -> str:
        return "HIT" if self.matched else "MISS"


def evaluate(
    cues: List[GTCue],
    events: List[MotionEvent],
    tolerance_s: float = 0.0,
) -> Tuple[List[CueResult], dict]:
    results: List[CueResult] = []
    for cue in cues:
        cr = CueResult(cue=cue)
        ws = cue.start_s - tolerance_s
        we = cue.end_s + tolerance_s
        for ev in events:
            if _overlap_s(ev.start_video_s, ev.end_video_s, ws, we) > 0:
                cr.matched.append(ev)
        results.append(cr)

    total_gt = len(cues)
    hit = sum(1 for r in results if r.status_label == "HIT")
    miss = sum(1 for r in results if r.status_label == "MISS")

    matched_event_ids = set()
    for r in results:
        for ev in r.matched:
            matched_event_ids.add(id(ev))
    total_events = len(events)
    fp = total_events - len(matched_event_ids)

    recall = hit / total_gt if total_gt else 0.0
    precision = len(matched_event_ids) / total_events if total_events else 0.0

    return results, dict(
        total_gt=total_gt,
        hit=hit,
        miss=miss,
        recall=recall,
        total_events=total_events,
        fp=fp,
        precision=precision,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _fmt_s(s: float) -> str:
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


def print_report(
    results: List[CueResult],
    metrics: dict,
    wall_t0: datetime,
    video_t0: float,
    quiet: bool = False,
):
    if not quiet:
        header = f"{'#':>3}  {'Window':>11}  {'Status':<6}  {'Hits':>4}  Label"
        print(header)
        print("-" * len(header))
        for r in results:
            cue = r.cue
            win = f"{_fmt_s(cue.start_s)}-{_fmt_s(cue.end_s)}"
            print(f"{cue.index:>3}  {win:>11}  {r.status_label:<6}  "
                  f"{len(r.matched):>4}  {cue.label}")
        print()

    m = metrics
    print("=" * 60)
    print(f"  Anchor         : wallclock={wall_t0.isoformat()}  video_s={video_t0}")
    print(f"  GT cues        : {m['total_gt']}")
    print(f"  HIT            : {m['hit']}")
    print(f"  MISS           : {m['miss']}  (no overlapping motion event)")
    print(f"  Recall         : {m['recall']*100:.1f}%  (HIT / total_gt)")
    print("-" * 60)
    print(f"  Motion events  : {m['total_events']}")
    print(f"  False pos      : {m['fp']}  (motion event with no GT overlap)")
    print(f"  Precision      : {m['precision']*100:.1f}%")
    print("=" * 60)
    print("Note: prefilter_skip events are not visible to the webhook, so")
    print("      MISS combines 'motion-detector miss' and 'prefilter dropped'.")
    print("      For a per-state breakdown use the prototype's")
    print("      eval_prefilter_coverage.py against pipeline.db instead.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Evaluate prefilter coverage from webhook motion events."
    )
    ap.add_argument("--srt", required=True, help="Ground-truth SRT file path")

    src = ap.add_mutually_exclusive_group()
    src.add_argument(
        "--events-url",
        default="http://localhost:9999/recorded_events/motion",
        help="Mock webhook endpoint returning {events:[...]} JSON",
    )
    src.add_argument(
        "--events-json",
        help="Local JSON file (same shape as the endpoint above)",
    )

    ap.add_argument("--source-id", help="Restrict to events from this source_id")

    ap.add_argument(
        "--analytics-url", default="http://localhost:8999",
        help="videostream-analytics service base URL (used by --anchor-mode stream-start)",
    )
    ap.add_argument(
        "--anchor-mode",
        choices=["stream-start", "first-event", "wallclock"],
        default="stream-start",
        help=(
            "How wall-clock ISO maps to video seconds. "
            "stream-start: query /sources/{id} (recommended). "
            "first-event: use earliest motion event (drifts; offline-friendly). "
            "wallclock: explicit --anchor-wallclock."
        ),
    )
    ap.add_argument(
        "--anchor-wallclock",
        help="ISO timestamp mapping to --ss (used with --anchor-mode wallclock)",
    )
    ap.add_argument(
        "--ss", type=float, default=0.0,
        help="Video-time seconds at the anchor (matches ffmpeg `-ss N`; default 0)",
    )

    ap.add_argument(
        "--tolerance", type=float, default=0.0,
        help="Seconds to expand each GT window on both sides (default 0)",
    )
    ap.add_argument(
        "--exclude-label-pattern",
        help=(
            "Regex (case-insensitive). GT cues whose label matches are dropped "
            "before evaluation. Useful for `[EMPTY]` cues in elder_wakeup where "
            "the room is empty and prefilter is *expected* to skip."
        ),
    )
    ap.add_argument("--quiet", action="store_true", help="Skip per-cue table")
    args = ap.parse_args()

    cues = parse_srt(args.srt, exclude_pattern=args.exclude_label_pattern)
    if not cues:
        print("ERROR: no cues parsed from SRT", file=sys.stderr)
        sys.exit(1)

    events = load_motion_events(
        events_url=None if args.events_json else args.events_url,
        events_json=args.events_json,
        source_id=args.source_id,
    )
    if not events:
        print("ERROR: no motion events found (source_id filter? webhook empty?)",
              file=sys.stderr)
        sys.exit(1)

    wall_t0, video_t0 = apply_anchor(
        events,
        anchor_mode=args.anchor_mode,
        anchor_wallclock=args.anchor_wallclock,
        ss=args.ss,
        analytics_url=args.analytics_url,
        source_id=args.source_id,
    )

    results, metrics = evaluate(cues, events, tolerance_s=args.tolerance)
    print_report(results, metrics, wall_t0, video_t0, quiet=args.quiet)


if __name__ == "__main__":
    main()
