# Benchmark — metro-ai-apps-recipe

Human-readable summary of the evaluation suite for the `metro-ai-apps-recipe`
skill. The suite compares agent output **with** the skill loaded against a
**baseline** run without it, using the cases in [`evals/evals.json`](evals/evals.json).

## Scope

The skill scaffolds a complete, vertical-agnostic computer-vision analytics
stack (DLSPS + MediaMTX/WebRTC + Coturn + Mosquitto + Node-RED + Grafana +
Nginx) on Intel hardware, with an optional SceneScape multi-camera
spatial-analysis path. Only the invoking prompt's model, class filter, alert
rule, dashboard, and MQTT topics change per use-case. It is **not** for
authoring a single DL Streamer pipeline in isolation, for model download alone,
or for cloud-only / Prometheus-OpenTelemetry metrics stacks.

## Eval cases

| ID | Case | Should trigger | Focus |
| -- | ---- | -------------- | ----- |
| 1 | Person detection, CPU, sample videos | Yes | Core seven-container topology, WebRTC video path, per-source MQTT, pinned tags |
| 2 | PPE compliance, GPU + classifier | Yes | `_gpu` variant, `group_add`, secondary classifier |
| 3 | Smart parking, RTSP sources | Yes | RTSP inputs, MediaMTX WHEP iframe, SAN cert, `--noproxy` curl |
| 4 | SceneScape multi-camera, RTSP | Yes | Opt-in `SCENESCAPE=yes` branch, delegation to `scenescape-setup` |
| 5 | Cloud Prometheus/OTel metrics | No | `DO NOT USE FOR` boundary — skill must not trigger |

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
Grafana plotting, and live annotated video delivered over WebRTC (DLSPS WHIP →
MediaMTX, Coturn ICE/TURN, browser WHEP embedded as Grafana `<iframe>` panels).
The skill's value is producing a stack that actually starts, stays running
(watchdog), and renders live data on the first try.

## How to (re)generate results

Quantitative pass-rate, token, and latency numbers are produced by the
multi-CLI eval runner, which drives the prompts in `evals/evals.json` through
the actual `SKILL.md` (with-skill) and against a neutral baseline
(without-skill), then LLM-grades each run against its `expectations` and
aggregates with skill-creator's `aggregate_benchmark`:

```bash
# Grab skill-creator's aggregation helpers (sparse checkout is enough):
git clone --depth 1 --filter=blob:none --sparse https://github.com/anthropics/skills.git /tmp/skills-ac
git -C /tmp/skills-ac sparse-checkout set skills/skill-creator

SKILL_CREATOR_DIR=/tmp/skills-ac/skills/skill-creator \
python3 /path/to/run_multi_cli_eval.py \
  --evals-json .github/skills/metro-ai-apps-recipe/evals/evals.json \
  --skill-path .github/skills/metro-ai-apps-recipe \
  --workspace /tmp/metro-eval-workspace \
  --clis copilot --configs with_skill,without_skill --grader-cli copilot
```

The heavy stack-generation cases (evals 1–3) need a generous `--timeout`
(≈900 s) to finish end-to-end; the negative case (eval 5) returns in seconds.
Read the aggregated numbers from `<workspace>/copilot/benchmark.json`.

### Results

Measured with the GitHub Copilot CLI as both executor and grader (5 eval
cases, 1 run each; per-eval pass rate = expectations satisfied / total):

| Eval | Case | With skill | Baseline |
| ---- | ---- | ---------- | -------- |
| 1 | Person detection, CPU, sample videos | 5/5 (100%) | 1/5 (20%) |
| 2 | PPE compliance, GPU + classifier | 4/5 (80%) | 1/5 (20%) |
| 3 | Smart parking, RTSP sources | 2/4 (50%) | 1/4 (25%) |
| 4 | SceneScape multi-camera | 4/4 (100%) | 0/4 (0%) |
| 5 | Cloud Prometheus/OTel (should NOT trigger) | 3/3 (100%) | 3/3 (100%) |

| Metric | With skill | Baseline |
| ------ | ---------- | -------- |
| Expectation pass rate (mean) | **86%** | 33% |
| Trigger accuracy (cases 1–5) | **5/5** | — |
| Mean tokens / run | ~1.70 M | ~0.55 M |
| Mean wall-clock / run | ~284 s | ~162 s |

The skill more than doubles the expectation pass rate (+53 pts) and correctly
holds the `DO NOT USE FOR` boundary on the cloud/metrics negative case (eval 5),
which both configurations recognize as out of scope. The token/time overhead
reflects the with-skill runs actually authoring the full multi-file stack rather
than sketching a high-level answer.