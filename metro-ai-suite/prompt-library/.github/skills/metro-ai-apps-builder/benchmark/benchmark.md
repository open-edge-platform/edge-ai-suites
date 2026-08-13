# Benchmark — metro-ai-apps-builder

Human-readable summary of the evaluation suite for the `metro-ai-apps-builder`
orchestrator skill. The suite compares agent behaviour **with** the skill loaded
against a **baseline** run without it, using the cases in
[`evals/evals.json`](evals/evals.json).

## Scope

The skill is a **conversational orchestrator**, not a builder. Given only a
business objective, it (1) runs a short business-objective Q&A, (2) discovers the
right open-edge-platform skill(s) via
[`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) and
[`references/DISCOVERY.md`](references/DISCOVERY.md), (3) proposes a plan with the
inferred technology, and (4) — **only after the user confirms** — builds by
delegating to those skill(s). It never asks the user to pick a framework, model,
precision, or device, and it never re-implements a delegate's work. It is **not**
the right skill when the user has already named a concrete skill (defer to that
skill directly) or wants a pure code answer with no deployable outcome.

## Eval cases

| ID | Case | Should trigger | Focus |
| -- | ---- | -------------- | ----- |
| 1 | Vision detection ("detect people, see alerts") | Yes | Business Q&A, routes to `metro-ai-apps-recipe`, plan-then-confirm, delegates the build |
| 2 | Document chatbot / RAG over PDFs | Yes | Routes to `chatqna-docker-deploy` (Helm variant for k8s), includes `npx skills add`, surfaces requirements |
| 3 | Video search over an archive | Yes | Sequences `vdms-dataprep-user` → `vss-deploy --search` → `vss-search-index`, confirms whole pipeline once |
| 4 | Train a custom defect detector | Yes | Routes to the `getitune-*` pipeline, INT8 quantization, offers follow-on deploy path |
| 5 | Ambiguous ("use AI with my cameras") | Yes | Clarifies in business terms before routing; no fabricated skills; no premature build |
| 6 | User names `metro-ai-apps-recipe` directly | No | Defers to the named skill instead of running its own Q&A/discovery |

## What "pass" means

Each case lists `expectations` that must appear in the behaviour/output. A run
passes a case when every expectation is satisfied. The negative case (eval 6)
passes when the orchestrator does **not** take over — confirming it hands off
when the user already named a concrete skill.

## Expected benefit of the skill

Without the skill, a baseline agent tends to either jump straight to one
technology it happens to know, or ask the user technology questions (which
model? CPU or GPU? Compose or Helm?) the user can't answer. It rarely maps a
vague business outcome to the correct open-edge-platform skill, rarely sequences
multi-skill pipelines (ingest → deploy → query; train → export → deploy), and
often starts building before confirming a plan.

With the skill, the agent:

- Keeps the conversation **business-only** and infers all technology itself.
- **Routes deterministically** to the right delegate(s) via the curated catalog,
  including multi-skill sequences and the Docker-vs-Helm split.
- **Plans and waits for confirmation** — nothing is created before approval.
- **Delegates** the build rather than re-implementing it, and verifies against
  the delegate's own completion criteria.
- **Holds the negative boundary** — steps aside when the user named a skill.

The skill's value is turning "I want to <outcome> on Intel edge" into the correct
buildable plan on the first try, without technology interrogation and without
premature or wrong-tool builds.

## How to (re)generate results

Quantitative pass-rate, token, and latency numbers are produced by the
multi-CLI eval runner, which drives the prompts in `evals/evals.json` through the
actual `SKILL.md` (with-skill) and against a neutral baseline (without-skill),
then LLM-grades each run against its `expectations` and aggregates with
skill-creator's `aggregate_benchmark`:

```bash
# Grab skill-creator's aggregation helpers (sparse checkout is enough):
git clone --depth 1 --filter=blob:none --sparse https://github.com/anthropics/skills.git /tmp/skills-ac
git -C /tmp/skills-ac sparse-checkout set skills/skill-creator

SKILL_CREATOR_DIR=/tmp/skills-ac/skills/skill-creator \
python3 /path/to/run_multi_cli_eval.py \
  --evals-json .github/skills/metro-ai-apps-builder/evals/evals.json \
  --skill-path .github/skills/metro-ai-apps-builder \
  --workspace /tmp/builder-eval-workspace \
  --clis copilot --configs with_skill,without_skill --grader-cli copilot
```

Because this skill **plans and delegates** rather than authoring a full stack
itself, grade it in **plan-only** mode: score the discovery + plan + confirmation
behaviour and the correctness of the chosen delegate(s), and stop before the
delegate build runs (mock or skip `npx skills add`). This keeps each run fast
(seconds to a couple of minutes) and isolates the orchestrator's decision quality
from the delegates' own benchmarks. Read the aggregated numbers from
`<workspace>/copilot/benchmark.json`.

### Results

Measured with the GitHub Copilot CLI as executor in **plan-only** mode (6 eval
cases, one with-skill run and one neutral baseline run each, N=1 per cell). Each
run was graded against its `expectations`; per-eval pass rate = expectations
satisfied / total. The build phase (`npx skills add` + delegate execution) was
skipped by design so the numbers isolate the orchestrator's discovery, routing,
and plan-before-build behaviour.

| Eval | Case | With skill | Baseline |
| ---- | ---- | ---------- | -------- |
| 1 | Vision detection → `metro-ai-apps-recipe` | 4/4 (100%) | 1/4 (25%) |
| 2 | Document chatbot → `chatqna-docker-deploy` | 4/4 (100%) | 1/4 (25%) |
| 3 | Video search → `vss-deploy` (+`vdms-dataprep-user`,`vss-search-index`) | 3/4 (75%) | 1/4 (25%) |
| 4 | Train defect model → `getitune-*` | 3/4 (75%) | 2/4 (50%) |
| 5 | Ambiguous ("use AI with my cameras") | 3/3 (100%) | 2/3 (67%) |
| 6 | User names `metro-ai-apps-recipe` (should NOT trigger) | 1/1 (100%) | 1/1 (100%) |

| Metric | With skill | Baseline |
| ------ | ---------- | -------- |
| Expectations passed (all cases) | **18/20 (90%)** | 8/20 (40%) |
| Expectation pass rate (mean per eval) | **92%** | 49% |
| Routing accuracy (correct delegate, evals 1–5) | **5/5** | 0/5 |
| Plan-before-build rate (no artifacts before confirmation) | **6/6** | 6/6 |
| Negative-case trigger accuracy (eval 6 defers) | **1/1** | 1/1 |
| Mean wall-clock / run | ~30 s | ~18 s |

The skill more than doubles the expectation pass rate (+50 pts overall, +43 pts
mean-per-eval) and lifts routing accuracy from 0/5 to 5/5: the baseline lands on
a plausible architecture but never names the correct open-edge-platform delegate
skill(s) or the exact `npx skills add` command, and on the vision case it leads
with technology (OpenVINO/DL Streamer/MQTT) instead of business questions. Both
configurations correctly hold the negative boundary (eval 6) and neither builds
before confirming, since the runs were graded plan-only. The two with-skill
misses were narrow: eval 3 did not explicitly offer the `vss-deploy-helm`
Kubernetes variant, and eval 4 did not surface the optional follow-on deploy
path (`model-download-user` → `metro-ai-apps-recipe`) after the IR is produced —
both are additive polish items, not routing errors.
