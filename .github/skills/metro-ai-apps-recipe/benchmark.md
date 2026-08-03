# Benchmark — metro-ai-apps-recipe

Human-readable summary of the evaluation suite for the `metro-ai-apps-recipe`
skill. The suite compares agent output **with** the skill loaded against a
**baseline** run without it, using the cases in [`evals/evals.json`](evals/evals.json).

## Scope

The skill scaffolds a complete, vertical-agnostic computer-vision analytics
stack (DLSPS + FFmpeg-HLS + Mosquitto + Node-RED + Grafana + Nginx) on Intel
hardware. Only the invoking prompt's model, class filter, alert rule, dashboard,
and MQTT topics change per use-case. It is **not** for authoring a single
DL Streamer pipeline in isolation or for model download alone.

## Eval cases

| ID | Case | Should trigger | Focus |
| -- | ---- | -------------- | ----- |
| 1 | Person detection, CPU, sample videos | Yes | Core six-container topology, per-source MQTT, pinned tags |
| 2 | PPE compliance, GPU + classifier | Yes | `_gpu` variant, `group_add`, secondary classifier |
| 3 | Smart parking, RTSP sources | Yes | RTSP inputs, HLS iframe, SAN cert, `--noproxy` curl |
| 4 | Retail queue, beginner, defaults | Yes | Batched questions, defaults, verify criteria |
| 5 | Single gvadetect pipeline string | No | Negative case — single-pipeline authoring |

## What "pass" means

Each case lists `expectations` that must appear in the output. A run passes a
case when every expectation is satisfied. Case 5 passes when the skill does
**not** trigger, confirming the `DO NOT USE FOR` boundary holds.

## Expected benefit of the skill

Without the skill, a baseline agent can describe individual components but
reliably misses the hard-won integration rules this recipe encodes: bypassing
the host proxy for localhost curl (`--noproxy '*' -k`), per-pipeline MQTT topic
layout, cgroup `group_add` for GPU/NPU, pinned image tags, a SAN in the
self-signed cert, class filtering in Node-RED, scalar (not JSON) count topics for
Grafana plotting, and HLS delivered via iframe + `player.html` with locally
bundled hls.js. The skill's value is producing a stack that actually starts,
stays running (watchdog), and renders live data on the first try.

## How to (re)generate results

Quantitative pass-rate, token, and latency numbers are produced by the
`skill-creator` eval workflow (Stages 5–7 of the Agent Skills Guide):

```bash
npx skills add anthropics/skills --skill skill-creator -a github-copilot
# Then: "Run evals for my skill at .github/skills/metro-ai-apps-recipe/"
```

Populate the table below from the generated `benchmark.json` after a run.

| Metric | With skill | Baseline |
| ------ | ---------- | -------- |
| Expectation pass rate | _tbd_ | _tbd_ |
| Trigger accuracy | _tbd_ | _tbd_ |
| Token overhead | _tbd_ | — |
