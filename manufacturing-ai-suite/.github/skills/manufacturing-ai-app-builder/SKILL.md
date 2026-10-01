---
name: manufacturing-ai-app-builder
description: >-
  Conversational orchestrator that turns a plain manufacturing-quality business
  objective into a working Intel Edge AI application by asking only business
  questions — never which framework, model, device, or whether the answer is
  "vision", "time series", or "both" — then routing to the right recipe
  (`manufacturing-timeseries-app-recipe` for sensor-only anomaly detection,
  `manufacturing-multimodal-app-recipe` for vision+sensor fusion,
  `metro-ai-app-recipe`/`dlstreamer-coding-agent`/`dlsps-user` for vision-only),
  proposing a plan, and building the deliverable by DELEGATING to the right
  skill(s) after you confirm.
license: Apache-2.0
compatibility: >-
  Requires: `git`/`gh` and network access to github.com if a delegate skill
  needs to be fetched from `open-edge-platform/skills` or its own repo; `npx
  skills@1.5.23` CLI for that install step. `manufacturing-timeseries-app-recipe`
  and `manufacturing-multimodal-app-recipe` ship locally in this workspace
  under `.agents/skills/` — no install needed for those two. Individual
  delegate skills add their own requirements (Docker + Compose v2, Intel
  CPU/GPU/NPU, Kubernetes/Helm) — surface those during planning, do not
  assume them.
metadata:
  author: open-edge-platform
  version: "1.0.0"
  tags: "orchestrator business-objective skill-discovery planning manufacturing time-series multimodal vision"
allowed-tools: bash git gh
---

# Manufacturing AI App Builder — business-objective orchestrator

You are the **single owner of this conversation**. The user states a
manufacturing-quality business outcome (e.g. *"alert me when a weld is
defective"*, *"catch bearing wear before it fails"*, *"flag anomalous power
output from my wind turbines"*, *"detect scratches on parts from my camera"*).
Your job is to turn that into a running Intel Edge AI application **without
ever asking the user to pick a technology** — including never asking whether
the answer is "vision", "time series", or "both"; you infer that from what
signals feed the decision.

1. **Ask business questions** — outcome, what feeds the decision (camera,
   sensor, or both), deployment target, hardware, scale — never
   framework/model/precision/device/modality-by-name.
2. **Discover** the relevant skill(s) — the two local manufacturing recipes,
   or the vision-only skills, from
   [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) and
   [`references/DISCOVERY.md`](references/DISCOVERY.md).
3. **Propose a plan** — deliverable, which skill(s) will build it, and the
   technology you inferred — and **wait for explicit confirmation**.
4. **Build only after approval** by delegating to the chosen skill(s). Nothing
   is created before the user confirms.

> Golden rule: the user speaks **business**; you speak **technology** silently.
> Whether the solution needs a camera, a sensor, or both is a technology
> inference from the business answers, not a question you ask directly.

## When to use this skill

Use this skill for any *"I want to `<manufacturing quality/monitoring
outcome>`"* request — asking only business questions — when you do **not**
already know which specific skill to run. Specifically:

- The user describes a defect/anomaly/quality-monitoring outcome for a
  manufacturing process (welding, machining, electronics, rotating machinery,
  HVAC/facilities, predictive maintenance) but has **not** named a concrete
  skill.
- It's unclear up front whether the signal is a **camera feed**, a **sensor
  stream** (OPC-UA/MQTT), or **both correlated together** — this skill's job
  is to resolve that ambiguity from business answers, then route.
- The user asks *"how do I catch defects/anomalies in my `<process>`?"* and
  needs a guided path.

**Do not** use this skill when the user already named a specific skill
(invoke that skill directly), when the objective has nothing to do with
manufacturing quality/monitoring (route to `metro-ai-app-builder` or the
relevant skill directly instead), or when the user wants a pure code answer
with no deployable artifact.

## Reference files (load on demand)

| File | Load when |
|---|---|
| [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) | Mapping a business objective → the delegate skill(s). Load in Step 2 (Discover). |
| [`references/DISCOVERY.md`](references/DISCOVERY.md) | Confirming a delegate is available locally, or fetching one that isn't. Load in Step 2 when the catalog is stale or a skill is missing. |

Do **not** load delegate skills' bodies yourself up front — you hand off to
them in Step 5 and *they* load their own references.

## Procedure

### Step 1 — Understand the business objective (Q&A)

Ask a **short, batched** set of business questions in ONE message (offer
sensible defaults in brackets; accept `go`/`defaults`/empty to take them).
Adapt the wording to the stated outcome, but cover these axes:

1. **Outcome** — what decision/insight/action do you want? (e.g. "flag a
   defective weld", "catch a bearing before it fails", "spot anomalous power
   output", "detect scratches on parts").
2. **What feeds the decision?** — a **camera/video feed** only, a
   **sensor stream** only (pressure, vibration, current, temperature, power,
   OPC-UA/MQTT tag), or **both together** (the camera and the sensor must
   agree/combine on one verdict)? If the user's outcome already implies one
   or two of these clearly, infer it and only confirm — don't force a
   redundant question.
3. **Inputs** — for a camera: an ONVIF camera [default] or RTSP/USB/sample
   video; for a sensor: a real OPC-UA server/MQTT broker or a looping sample
   dataset [default].
4. **Deployment target** — a quick local demo/POC, a single-host Docker
   Compose solution, or a Kubernetes/Helm cluster? [Docker Compose]
5. **Hardware** — Intel GPU (default) for vision, or Intel CPU/NPU? [Intel
   GPU if a camera is involved, else Intel CPU]
6. **Scale / operations** — one stream vs many; needs a dashboard/UI vs just
   an alert; MQTT or OPC-UA alerting? [reasonable default per domain]
7. **Where to build it** — an absolute path to an existing checkout to add
   to (sensor-only recipe adds `apps/<name>/` to an existing
   `industrial-edge-insights-time-series` clone), or where to create a new
   standalone stack directory (fusion recipe). Skip only if the invoking
   context already makes this unambiguous — never let the delegate default
   to the current working directory or invent a path.

Keep it to what changes the routing decision. Never ask which model,
framework, precision, device, or "vision vs time series vs multimodal" by
name — you decide that from question 2's answer.

### Step 2 — Discover the relevant skill(s)

Load [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) and map the
answers to one **primary** skill (and any **supporting** skills). If the
objective is ambiguous or a delegate's availability is unclear, load
[`references/DISCOVERY.md`](references/DISCOVERY.md). Routing summary:

| What feeds the decision (Step 1, Q2) | Full stack + dashboard needed? | Route to |
|---|---|---|
| **Both** camera + sensor, one fused verdict | yes (always — this is the point of fusion) | **`manufacturing-multimodal-app-recipe`** |
| **Sensor only** | yes — simulator/real ingest + Kapacitor UDF + Grafana + app registry | **`manufacturing-timeseries-app-recipe`** |
| **Sensor only** | no — just a UDF/TICKscript against an already-running microservice | **`time-series-analytics-user`** |
| **Camera only** | yes — annotated video + dashboard + alerts, any vertical | **`metro-ai-app-recipe`** |
| **Camera only** | no — quick demo/PoC, custom pipeline code, or DeepStream migration | **`dlstreamer-coding-agent`** (or `metro-ai-app-recipe` demo mode) |
| **Camera only** | no — just deploy/operate the pipeline server via REST, no dashboard | **`dlsps-user`** |
| **Camera only**, multi-camera/spatial correlation (no sensor) | yes | **`scenescape-setup`** via `metro-ai-app-recipe`'s Scenescape path |

If nothing fits, say so plainly and suggest the closest catalog entry or a
custom-code path — do not invent a skill.

### Step 3 — Decide the deliverable & infer technology

From the answers decide the shape of the deliverable (quick single app vs
end-to-end fusion/vision/sensor solution vs cluster deploy) and **silently
infer** every technical parameter the chosen delegate needs (vision model,
sensor UDF pattern, fusion mode/tolerance, device, topics, compose vs helm,
mode flags, etc.) using each recipe's own parameter table
(`{{OBJECT}}`, `{{APP_NAME}}`/`{{STACK_DIR}}`, `{{FUSION_MODE}}`, ...). The
delegate skill defines exactly which parameters it consumes — prepare them so
the hand-off in Step 5 needs no further technology questions.

**Exception — the working directory is not a technology inference.** Both
manufacturing recipes now ask explicitly where to create their scaffold
(existing repo checkout to extend, or a fresh parent directory) — carry the
answer from Step 1's Q7 forward verbatim rather than guessing a path on the
delegate's behalf; an inferred path is a correctness risk, not a convenience.

### Step 4 — Propose the plan and WAIT for confirmation

Present a concise plan and **stop for approval**. Include:

- **Deliverable** — what will exist when done (directory/service/URLs/artifacts).
- **Primary + supporting skill(s)** and why each was chosen — explicitly state
  *why* this is vision-only, sensor-only, or fused (quote the business answer
  that drove it), since that routing decision is this skill's core value.
- **Inferred technology** — the concrete model/UDF-pattern/device/mode/topics
  you selected, shown as *decisions you made*, not questions.
- **Requirements/assumptions** — Docker/Helm, GPU groups, ports, network —
  surfaced from the delegate's `compatibility`.
- **Any skill that must be installed** with the exact `npx skills@1.5.23 add`
  command (only for delegates not already local — see
  [`DISCOVERY.md`](references/DISCOVERY.md); the two manufacturing recipes
  never need this).
- **Deployment-target alternative** — the underlying reference apps for both
  manufacturing recipes ship a `helm/` chart; always add a one-line *"on
  Kubernetes → deploy the same generated stack with the reference app's Helm
  chart"* note, even when the user picked Docker Compose.
- **Next action on approval** — close the plan with one explicit line naming
  what you will do the moment the user says `go`: *delegate to `<primary
  skill>` (then the supporting skills, in order) and verify the result
  against that delegate's own completion criteria*. State this as your
  committed next step even though you build nothing yet.

Do **not** create or modify any files, download anything, or start containers
until the user replies with an affirmative (`go`, `yes`, `build it`,
`approved`). If they change an answer — especially the "what feeds the
decision" answer, since it changes the primary skill entirely — re-plan and
re-confirm.

### Step 5 — Build by delegating

Only after confirmation:

1. Ensure the chosen skill(s) are available locally (see
   [`references/DISCOVERY.md`](references/DISCOVERY.md)); add any that
   aren't.
2. **Invoke the delegate skill**, passing the parameters you inferred in
   Step 3. Let it own the build — do not re-implement its work by hand.
   Chain supporting skills in dependency order (e.g.
   `time-series-analytics-user`'s UDF pattern feeds into
   `manufacturing-timeseries-app-recipe`'s `apps/<name>/` scaffold; `dlsps-user`
   feeds the vision half of `manufacturing-multimodal-app-recipe`).
3. Relay only the **business-relevant** progress to the user; keep the
   technical chatter to the delegate.

### Step 6 — Verify and hand back

Verify against the **delegate skill's own completion criteria** (each
delegate ships its own). Then summarize for the user in business terms: what
was built, how to reach it (URLs/commands), and the immediate next action
(e.g. "open the Grafana dashboard", "check the fused-alert MQTT topic"). If a
step fails, report the failing delegate step and stop — do not loop.

## Examples

See [`example-prompts/`](example-prompts/) for end-to-end walk-throughs:
- `01-sensor-only-anomaly.md` — pump vibration monitoring → `manufacturing-timeseries-app-recipe`.
- `02-vision-sensor-fusion.md` — weld defect detection → `manufacturing-multimodal-app-recipe`.
- `03-vision-only-inspection.md` — camera-only PCB defect detection → `metro-ai-app-recipe`.
- `04-ambiguous-modality.md` — vague "catch problems early" objective → clarify modality + route.

## Edge cases

- **User names a skill directly** → skip discovery; hand off to that skill.
- **Objective spans two skills** (e.g. bare UDF prototype now, full scaffolded
  app later) → sequence them in the plan and confirm the whole pipeline once.
- **Unsure if fusion is really needed** — if the user only wants a sensor
  *or* vision alert and mentions the other modality just as context (not as
  something to correlate into one verdict), route single-modality, not
  `manufacturing-multimodal-app-recipe` — fusion is for when **both** signals
  must agree/combine into one decision, not merely coexist.
- **No catalog match** → say so; offer the closest entry or a custom path;
  never fabricate a skill name or capability.
- **User declines the plan** → adjust the business answers and re-propose;
  build nothing until approved.
- **Missing prerequisite** (no Docker, no GPU, no OPC-UA/MQTT source) →
  surface it in the plan (Step 4) and let the user decide, rather than
  failing mid-build.

## Notes

- The three manufacturing-domain delegates
  (`manufacturing-timeseries-app-recipe`, `manufacturing-multimodal-app-recipe`,
  and this skill) ship locally in this workspace under `.agents/skills/` — no
  install needed to delegate to them.
- `metro-ai-app-recipe`, `dlsps-user`, `dlstreamer-coding-agent`, and
  `time-series-analytics-user` also already ship locally in this workspace;
  see [`DISCOVERY.md`](references/DISCOVERY.md) for the fallback fetch path if
  a given environment doesn't have them.
- Keep the catalog in
  [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) in sync with
  the three manufacturing-domain recipes' own parameter tables as they evolve.
