# Benchmark — security-review

Human-readable summary of the evaluation suite for the `security-review` skill.
The suite compares agent output **with** the skill loaded against a **baseline**
run without it, using the cases in [`evals/evals.json`](evals/evals.json).

## Scope

The skill provides on-demand, development-time security review across four
surfaces: secure code review, AI-generated code guardrails, container artifacts
(Dockerfile / Compose), and Helm / Kubernetes defaults. Runtime, host, cluster,
and organizational controls are out of scope.

## Eval cases

| ID | Case | Should trigger | Focus |
| -- | ---- | -------------- | ----- |
| 1 | Dockerfile review | Yes | Floating tag, embedded secret, ADD vs COPY, root user |
| 2 | FastAPI endpoint review | Yes | `eval()` on untrusted input, raw dict body, payload logging |
| 3 | Helm pod security | Yes | `runAsNonRoot`, `allowPrivilegeEscalation`, pinned tag |
| 4 | AI-generated install script | Yes | `curl \| sh`, `--trusted-host`, hardcoded secret |
| 5 | README formatting | No | Negative case — style task, no security relevance |

## What "pass" means

Each case lists `expectations` that must appear in the output. A run passes a
case when every expectation is satisfied. Case 5 passes when the skill does
**not** trigger, confirming the `DO NOT USE FOR` boundary holds.

## Expected benefit of the skill

Without the skill, a baseline agent typically catches obvious issues (a
hardcoded secret) but is inconsistent about: classifying findings as
"Fix in artifact" vs "Deployment-time responsibility", assigning severity **and**
confidence, and applying the AI-generated-code trust model (treating generated
snippets as untrusted draft, rejecting `curl | sh`). The skill's value is a
consistent, classified, severity-and-confidence-rated output format and the
explicit development-time scope boundary.

## How to (re)generate results

Quantitative pass-rate, token, and latency numbers are produced by the
`skill-creator` eval workflow (Stages 5–7 of the Agent Skills Guide):

```bash
npx skills add anthropics/skills --skill skill-creator -a github-copilot
# Then: "Run evals for my skill at .github/skills/security-review/"
```

Populate the table below from the generated `benchmark.json` after a run.

| Metric | With skill | Baseline |
| ------ | ---------- | -------- |
| Expectation pass rate | _tbd_ | _tbd_ |
| Trigger accuracy | _tbd_ | _tbd_ |
| Token overhead | _tbd_ | — |
