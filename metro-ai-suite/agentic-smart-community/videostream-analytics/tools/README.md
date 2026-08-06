# tools/

Validation utilities for `videostream-analytics`. These are *not* unit/integration
tests — they require a ground-truth SRT and either a running mock webhook or an
exported events JSON. Keep them out of `tests/` so pytest discovery stays clean.

Current video corpus layout (relative to repo root):
- `../demo/videos/cam_child/...`
- `../demo/videos/cam_fridge/...`
- `../demo/videos/cam_elder_bedroom/...`
- `../demo/videos/cam_elder_bedroom_2/...`

## Quick map

| Tool | Use when |
|---|---|
| `run_eval.sh` | run a scenario end-to-end and print prefilter Recall/Precision |
| `eval_prefilter_from_webhook.py` | re-evaluate a saved events dump (offline replay) |
| `render_eval_timeline.py` | eyeball *why* a cue was MISS or an event was FP — ASCII timeline |

## render_eval_timeline.py — debug-level timeline visualization

Reads the same `events.json` + GT SRT (+ optional `status.json` for an exact
anchor) as `eval_prefilter_from_webhook.py` and prints a side-by-side ASCII
timeline. Pure stdout, no matplotlib — works over SSH and in CI logs.

When to use it: a Recall < 100% or a non-zero FP count from `run_eval.sh`.
The timeline tells you whether the gap is a *detection* problem (cue has no
event nearby at all) or a *time-window alignment* problem (event is right
next to the cue but missed by a fraction of a second — `--tolerance 2.0`
recovers those).

```bash
# Use the dumps run_eval.sh leaves behind (file paths printed at end of run):
.venv/bin/python tools/render_eval_timeline.py \
  --srt ../demo/videos/cam_fridge/demo006-2_expanded_20min_v2_groundtruth.srt \
    --events-json /tmp/fridge_events_<pid>.json \
    --status-json /tmp/fridge_status_<pid>.json \
    --source-id cam_fridge --ss 0

# Loosen overlap match by ±2s — same flag as the evaluator:
.venv/bin/python tools/render_eval_timeline.py ... --tolerance 2.0

# Drop [EMPTY] cues so they don't pollute the picture (elder scenarios):
.venv/bin/python tools/render_eval_timeline.py ... --exclude-label-pattern '\[EMPTY\]'
```

Output anatomy: GT cues stacked above (`[==X==]` MISS, `[==D==]` HIT-danger,
etc.), motion events stacked below (`{----}` HIT, `{****}` FP), shared time
axis at the bottom. Followed by the same Recall/Precision summary you'd get
from the evaluator.

## run_eval.sh — one-shot end-to-end evaluation across all scenarios

Wraps the manual recipe (mediamtx → mock webhook → analytics → ffmpeg push →
register source → wait → evaluate) for every demo scenario into one
command. Trap-based cleanup so nothing leaks on Ctrl-C.

### Scenarios

The demo covers 3 use cases (`child_safety`, `elder_wakeup`,
`refrigerator_monitor`); they expand to 4 scenarios because `elder_wakeup`
has 2 input videos. (`use_case` is only a label here — it is not part of the
register API; per-scenario behavior comes from the `pipeline` config.)

| Scenario | source_id | Demo use case | Video | ss | Prefilter | GT |
|---|---|---|---|---|---|---|
| `child` | cam_child | child_safety | `VSA_EVAL_CHILD_VIDEO` | 40 | on | yes |
| `fridge` | cam_fridge | refrigerator_monitor | `VSA_EVAL_FRIDGE_VIDEO` | 0 | **off** | yes (4 [TAKE] cues) |
| `elder_day1` | cam_elder_bedroom | elder_wakeup | `VSA_EVAL_ELDER_VIDEO` | 0 | on | yes (excl `[EMPTY]`) |
| `elder_day2` | cam_elder_bedroom_2 | elder_wakeup | `VSA_EVAL_ELDER_2_VIDEO` | 0 | on | yes (excl `[EMPTY]`) |

Notes:
- Set the corresponding `VSA_EVAL_*_VIDEO` variables to local MP4 files before running an evaluation. Videos are not distributed with the repository.
- `fridge` runs with `prefilter.enabled=false` because `target_classes=["person"]`
  would filter out hand-only motion.
- `elder_*` GT cue 3 is `[EMPTY]` (no person); the eval excludes it via
  `--exclude-label-pattern '\[EMPTY\]'` so Recall reflects only real
  `[SLEEPING]` / `[WAKEUP]` cues.

### Usage

```bash
# All 4 scenarios, sequentially (longest path: ~20 min for fridge alone).
bash tools/run_eval.sh

# Single scenario
bash tools/run_eval.sh --scenario child
bash tools/run_eval.sh --scenario fridge
bash tools/run_eval.sh --scenario elder_day1
bash tools/run_eval.sh --scenario elder_day2

# Smoke mode — much shorter waits (60-120s per scenario), useful to
# verify pipeline plumbing without waiting for full GT coverage.
bash tools/run_eval.sh --wait-mode short

# Leave services running after the last scenario (manual cleanup).
bash tools/run_eval.sh --keep

# Env knobs (rarely needed)
MEDIAMTX_BIN=~/bin/mediamtx bash tools/run_eval.sh
ANALYTICS_PORT=18999 bash tools/run_eval.sh
```

### What it does

1. Boots shared infra **once**: MediaMTX (if `:8554` free; reuses otherwise) +
   mock webhook on `:9999` + analytics on `:8999`.
2. For each requested scenario:
   - Clears `/recorded_events` (so dumps don't mix across scenarios)
   - ffmpeg pushes the scenario's video with the right `--ss`
   - Registers the source with the right `use_case` and prefilter setting
   - Sleeps `<wait>` seconds (`full` mode = covers all GT cues; `short` = smoke)
   - Snapshots `/recorded_events` + `/sources/{id}` to `/tmp/<scen>_events_<pid>.json`
     and `/tmp/<scen>_status_<pid>.json`
   - Runs `eval_prefilter_from_webhook.py` in `--anchor-mode stream-start`
     (with `--exclude-label-pattern '\[EMPTY\]'` for elder scenarios)
   - Stops the source + ffmpeg before moving on
3. On EXIT/INT/TERM: stops all sources, kills mock + analytics + ffmpeg + (if
   we started it) mediamtx. `--keep` skips step 3 and prints the PIDs.

Pre-flight refuses to start if `:8999` or `:9999` are already taken — usually
a stale `uvicorn` from a previous `--keep` run. The error message gives you
the exact `kill $(lsof ...)` command.

## eval_prefilter_from_webhook.py

Computes prefilter `Recall` and `Precision` against a GT SRT, reading motion
events from the mock webhook (or a saved dump of it).

### Why `--ss` and `--anchor-mode` matter

This service is RTSP-only: events carry wall-clock ISO timestamps, never
video seconds. A GT SRT cue, on the other hand, is in *video time* (seconds
since stream start). So we need to align wall-clock T0 to a known point in
the video.

Three modes (recommended → fallback):

| mode | wall-clock T0 source | accuracy | requires |
|---|---|---|---|
| `stream-start` (default) | `GET /sources/{id}` → `health.start_time` | exact | service running, `--source-id` |
| `first-event` | earliest motion event's `start_time` | drifts by 5-15s (motion warmup) | nothing |
| `wallclock` | `--anchor-wallclock <ISO>` | as accurate as you measure | manual |

`--ss` is video-time T0: pass the same value you used for ffmpeg `-ss N` when
pushing the demo video. For `scripts/test-videostream-analytics.sh` this is
`40` for child, `0` for fridge/elder.

### End-to-end recipe (recommended)

The easiest path is `run_eval.sh`, which drives the whole flow and evaluates
at the end. To re-evaluate manually against a live service:

```bash
cd videostream-analytics

# 1. Run a scenario with --keep so the services stay up afterwards:
VSA_EVAL_CHILD_VIDEO=<path-to-child.mp4> bash tools/run_eval.sh --scenario child --keep

# 2. Re-evaluate while the service is still up (e.g. with a different
#    tolerance). --anchor-mode stream-start asks the service for the real
#    stream-open time.
.venv/bin/python tools/eval_prefilter_from_webhook.py \
  --srt ../demo/videos/cam_child/child_safety_demo_groundtruth.srt \
    --source-id cam_child --ss 40
```

(The same flow works against `scripts/test-videostream-analytics.sh --local
--integration-only`, but that suite registers short-lived `test_*` sources
rather than `cam_child`, so pass the matching `--source-id`.)

### Offline replay (after service shut down)

Dump events to disk before the test script's cleanup runs, then replay anytime:

```bash
# during the test run:
curl -s http://localhost:9999/recorded_events > /tmp/child_events.json

# anytime later — note: first-event anchor drifts, so HIT/MISS may shift
# by ±10s for cues near the video start. For exact replay, snapshot
# /sources/cam_child as well and use --anchor-mode wallclock.
.venv/bin/python tools/eval_prefilter_from_webhook.py \
    --srt <gt.srt> --events-json /tmp/child_events.json \
    --source-id cam_child --anchor-mode first-event --ss 40
```

### What it can NOT measure

- `prefilter_skip` count, skip rate, `PARTIAL` status.
  The service posts events to a webhook and never persists tasks locally;
  the prefilter stays silent on skip, so anything that motion+prefilter
  together dropped just shows up as `MISS`.

- VLM alert accuracy (Recall/Precision/F1, alert latency).
  That belongs to the MCP Server side, which owns the alerts produced from
  the `videostream-analytics → /events → VLM → alert` link.
