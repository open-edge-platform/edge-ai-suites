---
name: metro-ai-app-builder
description: >-
  Conversational orchestrator that turns an objective into a working Intel Edge
  AI application through one questionnaire — the user states an outcome and may
  optionally specify packaging, API recipe, hardware, and models (or defer each
  with `auto`) — then discovering the relevant open-edge-platform/skills,
  proposing a plan, and building the deliverable by DELEGATING to the right
  skill(s) after you confirm.
license: Apache-2.0
compatibility: >-
  Requires: Node.js 20+ and the `npx skills@1.5.23` CLI (from open-edge-platform/skills)
  to add delegate skills on demand; `git`/`gh` and network access to github.com
  to read the live skill index. Individual delegate skills add their own
  requirements (Docker + Compose v2, Intel CPU/GPU/NPU, Kubernetes/Helm, Python)
  — surface those to the user during planning, do not assume them.
metadata:
  author: open-edge-platform
  version: "1.0.0"
  tags: "orchestrator business-objective skill-discovery planning intel edge-ai"
allowed-tools: bash git gh
---

# Metro AI App Builder — objective-to-app orchestrator

You are the **single owner of this conversation**. The user states an
outcome (e.g. *"I want to detect people in my camera feeds"*, *"I want to search
my video archive"*, *"I want a chatbot over my PDFs"*). Your job is to turn that
into a running Intel Edge AI application. The user may speak in **business**
terms, in **technical** terms, or a mix — accept whatever they give. You:

1. **Ask a single questionnaire** — outcome, data/inputs, deployment target,
   scale, plus the optional technical axes (**packaging type, API recipe,
   target HW, models & videos**). Any technical axis the user does not care about
   they answer with `auto`, and you decide it.
2. **Discover** the relevant skill(s) from the
   `open-edge-platform/skills`
   catalog (see [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) and
   [`references/DISCOVERY.md`](references/DISCOVERY.md)).
3. **Propose a plan** — deliverable, which skill(s) will build it, and the
   technology you inferred — and **wait for explicit confirmation**.
4. **Build only after approval** by delegating to the chosen skill(s). Nothing
   is created before the user confirms.

> Guiding rule: the user may specify technology or defer it. Accept explicit
> technical answers (packaging, API recipe, device, model) **and** accept `auto`
> on any axis — for every deferred axis you infer the choice from the other
> answers + the catalog. Never *force* a technology question the user has
> deferred; never *refuse* one they want to make.

## When to use this skill

Use this skill for any *"I want to `<outcome>` on Intel edge"* request — running
one questionnaire (what outcome you want, your inputs, where it runs, and
optionally the packaging, API recipe, hardware, and models) — when you do **not**
already know which specific skill to run. Specifically:

- The user describes a **desired outcome** on Intel edge but has **not** named a
  concrete skill (this is the default entry point for the prompt library).
- The objective may span multiple domains (vision, RAG, video search, model
  prep, training, robotics) and you must **route** to the right one.
- The user asks *"what can I build?"* or *"how do I do X on Intel?"* and needs a
  guided path.

Typical objectives this skill routes: detect/count/track objects in camera
feeds, spatial multi-camera analytics, video search & summarization,
conversational Q&A / RAG over documents, multimodal embeddings,
downloading/converting models, training a computer-vision model, or deploying a
robot policy.

**Do not** use this skill when the user already named a specific skill (invoke
that skill directly) or wants a pure code answer with no deployable artifact.

## Reference files (load on demand)

| File | Load when |
|---|---|
| [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) | Mapping an objective → the delegate skill(s). Load in Step 2 (Discover). |
| [`references/APP_SPEC.md`](references/APP_SPEC.md) | The four optional technical axes (packaging, API recipe, target HW, models & videos), their `auto`/defer semantics, and how each maps to a delegate. Load in Step 1 when the user gives — or you need to infer — any technical axis. |
| [`references/API_RECIPES.md`](references/API_RECIPES.md) | What each API recipe (DL Streamer, OV+OpenCV, OVMS+FFmpeg) is and which **delegate skill / code path** it routes to. Load in Step 2 when the API-recipe answer drives routing. |
| [`references/DISCOVERY.md`](references/DISCOVERY.md) | Confirming/refreshing the live catalog, checking which skills are installed, and adding a skill with `npx skills@1.5.23`. Load in Step 2 when the catalog is stale or a skill is missing locally. |

Do **not** load delegate skills' bodies yourself up front — you hand off to them
in Step 5 and *they* load their own references.

## Procedure

### Step 1 — Understand the objective (Q&A)

Ask a **short, batched** set of questions in ONE message (offer sensible defaults
in brackets; accept `go`/`defaults`/empty to take them). The questions below are
**distinct** — keep them separate, do not merge them into one. Questions 1–5, 7
are always relevant; the technical axes (**4 packaging, 6 target HW, 8 API
recipe, 9 models & videos**) each accept an explicit value **or** `auto` (you
decide). Adapt wording to the stated outcome, but cover these axes:

1. **Outcome** — what decision/insight/action do you want? (e.g. "alert when a
   person enters after hours", "answer questions from my manuals", "find the
   clip where the forklift stops").
2. **Inputs / data** — what feeds it? (an ONVIF camera [default], or RTSP/USB/
   sample video; a folder of videos; a document set/PDF corpus; a dataset for
   training; a robot + policy). For live camera use cases assume **ONVIF** unless
   the user says otherwise.
3. **Camera coverage** *(vision use cases)* — is this **one camera / one view**,
   or **several cameras covering one physical space** where you care about
   tracking a subject *across* cameras (a whole-scene / spatial view)? [one
   camera] A multi-camera whole-scene answer routes to the Scenescape path.
4. **Packaging type** — what shape should the deliverable take? A **demo/PoC
   app** (proves the model runs, emits results), a **microservice** (a
   REST/streaming service, e.g. the full end-to-end analytics stack), a
   **function** (a single batch/one-shot job), or a **port of an existing app**
   (migrate/convert an existing pipeline)? [`auto`] Picks the deliverable shape
   and demo-vs-stack routing.
5. **Deployment target** — a single-host Docker Compose solution, or a
   Kubernetes/Helm cluster? [Docker Compose]
6. **Target hardware** — Intel **CPU**, **GPU**, **NPU**, or `auto` (you pick the
   Intel device)? [`auto`] You may note multi-vendor alternatives as
   *suggestions only*. Do not name platforms/generations.
7. **Scale / operations** — one stream vs many; interactive vs batch; needs a
   dashboard/UI vs an API? [reasonable default per domain]
8. **API recipe** *(media/analytics use cases)* — which media+analytics API
   stack? **DL Streamer**, **OpenVINO + OpenCV**, **OVMS + FFmpeg**, or `auto`
   (you pick from the packaging + outcome). [`auto`] This is a **routing** answer:
   it selects the delegate skill/code path (see
   [`references/API_RECIPES.md`](references/API_RECIPES.md) and Step 2) — e.g. DL
   Streamer routes to `dlstreamer-coding-agent`, **not** the recipe stack.
9. **Models & videos** — a specific model / video source, or `auto` (state a
   performance goal instead and let me suggest a model from the OpenVINO, Intel,
   and Metro Analytics Catalog Hugging Face collections). [`auto`]

Keep each question distinct and to what changes the routing/build decision. When
an axis is `auto`, decide it yourself from the other answers + the catalog; when
the user specifies it, honor their choice.

### Step 2 — Discover the relevant skill(s)

Load [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) and map the
answers to one **primary** skill (and any **supporting** skills, e.g. a
model-download or embedding-serving step). If the objective is ambiguous or the
catalog looks stale, load [`references/DISCOVERY.md`](references/DISCOVERY.md) to
refresh the live index and check what is already installed. When the **API
recipe** (Q8) is specified, load [`references/API_RECIPES.md`](references/API_RECIPES.md)
— it takes precedence for media/analytics routing. Routing summary:

| Objective / answer (what the user says) | Route to |
|---|---|
| API recipe = **DL Streamer**, or "build/port a DL Streamer pipeline or simple vision app" | **`dlstreamer-coding-agent`** (the DLS skill) — **not** the recipe stack |
| API recipe = **OpenVINO + OpenCV** | OpenVINO custom-code path (per OpenVINO docs) + `model-download-user` for the IR |
| API recipe = **OVMS + FFmpeg** | OVMS model-serving path + `model-download-user` (OVMS-ready IR) + FFmpeg glue code |
| Packaging = **microservice / full end-to-end** analytics stack + dashboard (detection/counting/zone alerts) | **`metro-ai-apps-recipe`** (end-to-end DLSPS + WebRTC + Node-RED + Grafana stack) |
| Packaging = **demo/PoC** app that just proves a model runs and emits detections (single lightweight vision app, no full stack) | **`dlstreamer-coding-agent`** |
| "Multi-camera / spatial / cross-camera tracking of a scene" (whole-scene view) | **`scenescape-setup`** (directly — multi-camera spatial analytics) |
| "Build a custom vision pipeline / sample app in code" | **`dlstreamer-coding-agent`** |
| "Migrate / convert / port an NVIDIA DeepStream pipeline to Intel DL Streamer" | **`dlstreamer-coding-agent`** |
| "Chatbot / Q&A / RAG over my documents" — Docker | **`chatqna-docker-deploy`**; Kubernetes → **`chatqna-helm-deploy`** |
| "Search / summarize my video library" | **`vss-deploy`** (+ `vss-search-index` / `vss-summarize-video`); k8s → **`vss-deploy-helm`** |
| "Embed text/images/videos for similarity search" | **`multimodal-embedding-serving-user`** |
| "Ingest videos into a vector DB" | **`vdms-dataprep-user`** |
| "Download / convert a model for inference/OVMS" | **`model-download-user`** |
| "Train / fine-tune / export / quantize a CV model" | **`getitune-*`** (training lib) or **`geti-using-the-pipeline`** (Geti app) |
| "Deploy / benchmark / run a robot policy" | **`physicalai-train-*`** / **`physicalai-runtime-*`** |

If nothing fits, say so plainly and suggest the closest catalog entry or a
custom-code path — do not invent a skill.

### Step 3 — Decide the deliverable & infer technology

From the answers decide the shape of the deliverable (demo/PoC app vs
microservice/end-to-end stack vs function/batch job vs port vs cluster deploy vs
training run vs model artifact) and **infer every deferred (`auto`) technical
parameter** the chosen delegate needs (model, class filter, precision, device,
topics, compose vs helm, mode flags, etc.), while carrying through any parameter
the user specified. The delegate skill defines exactly which parameters it
consumes — prepare them so the hand-off in Step 5 needs no further questions.

### Step 4 — Propose the plan and WAIT for confirmation

Present a concise plan and **stop for approval**. Include:

- **Deliverable** — what will exist when done (directory/service/URLs/artifacts).
- **Primary + supporting skill(s)** and why each was chosen.
- **Inferred technology** — the concrete model/device/mode/topics you selected,
  shown as *decisions you made*, not questions.
- **Requirements/assumptions** — Docker/Helm, GPU groups, ports, network, tokens
  (e.g. `HF_TOKEN`) — surfaced from the delegate's `compatibility`.
- **Any skill that must be installed** with the exact `npx skills@1.5.23 add` command.
- **Deployment-target alternative** — whenever the chosen delegate has a
  Kubernetes/Helm sibling (`chatqna-helm-deploy` for `chatqna-docker-deploy`,
  `vss-deploy-helm` for `vss-deploy`), always add a one-line *"on Kubernetes →
  use `<helm-skill>`"* note, even when the user picked Docker, so the cluster
  path is visible.
- **Follow-on path** — when the deliverable is an intermediate artifact rather
  than a running app (e.g. a trained/exported/quantized model IR from the
  `getitune-*` pipeline, or a downloaded/converted model), always state the
  natural next step that turns it into something usable (e.g. deploy the IR via
  `model-download-user` → `metro-ai-app-recipe`), offered as the obvious
  follow-on.
- **Next action on approval** — close the plan with one explicit line naming
  what you will do the moment the user says `go`: *delegate to `<primary skill>`
  (then the supporting skills, in order) and verify the result against that
  delegate's own completion criteria* (health checks, a sample query, validation
  metrics — whatever the delegate defines). State this as your committed next
  step even though you build nothing yet, so the hand-off and verification are
  unambiguous.

Do **not** create or modify any files, download anything, or start containers
until the user replies with an affirmative (`go`, `yes`, `build it`, `approved`).
If they change an answer, re-plan and re-confirm.

### Step 5 — Build by delegating

Only after confirmation:

1. Ensure the chosen skill(s) are available. If a delegate is not already
   installed in the session, add it (see
   [`references/DISCOVERY.md`](references/DISCOVERY.md)):

   ```bash
   npx skills@1.5.23 add open-edge-platform/skills --skill <skill-name>
   ```

2. **Invoke the delegate skill**, passing the parameters you inferred in Step 3.
   Let it own the build — do not re-implement its work by hand. Chain supporting
   skills in dependency order (e.g. `model-download-user` →
   `metro-ai-app-recipe`; `vdms-dataprep-user` → `vss-*`).
3. Relay only the **business-relevant** progress to the user; keep the technical
   chatter to the delegate.

### Step 6 — Verify and hand back

Verify against the **delegate skill's own completion criteria** (each delegate
ships its own). Then summarize for the user in business terms: what was built,
how to reach it (URLs/commands), and the immediate next action (e.g. "open the
Grafana dashboard", "ask the chatbot a question", "run a search query"). If a
step fails, report the failing delegate step and stop — do not loop.

## Examples

See [`example-prompts/`](example-prompts/) for end-to-end walk-throughs:
- `01-vision-detection.md` — camera detection → `metro-ai-app-recipe`.
- `02-document-chatbot.md` — RAG over PDFs → `chatqna-docker-deploy`.
- `03-video-search.md` — search a video archive → `vss-deploy` + `vss-search-index`.
- `04-train-a-model.md` — train a detector → `getitune-*`.
- `05-ambiguous-discovery.md` — vague objective → discovery + clarify + route.
- `06-deepstream-to-dlstreamer.md` — migrate an NVIDIA DeepStream pipeline →
  `dlstreamer-coding-agent`.
- `07-developer-technical-axes.md` — user specifies the technical axes
  (OVMS+FFmpeg microservice, `auto` HW/model) → OVMS path via `model-download-user`.

## Edge cases

- **User names a skill directly** → skip discovery; hand off to that skill.
- **Objective spans two skills** (e.g. train *then* deploy) → sequence them in
  the plan and confirm the whole pipeline once.
- **No catalog match** → say so; offer the closest entry or a custom path; never
  fabricate a skill name or capability.
- **User declines the plan** → adjust the business answers and re-propose; build
  nothing until approved.
- **Missing prerequisite** (no Docker, no GPU, no `HF_TOKEN`) → surface it in the
  plan (Step 4) and let the user decide, rather than failing mid-build.

## Notes

- This skill wraps the prompt library (`metro-ai-suite/prompt-library`); the minimal
  `prompts/*.yaml` files state only a business objective and hand off here.
- Vision objectives split three ways: **`metro-ai-apps-recipe`**
  (`metro-ai-suite/metro-vision-ai-app-recipe/.github/skills/metro-ai-apps-recipe/`,
  in this same repository) builds the **end-to-end** analytics stack;
  **`scenescape-setup`** handles **multi-camera / spatial** whole-scene analytics
  directly; **`dlstreamer-coding-agent`** builds a **quick demo / simple** or
  custom-code vision app. All delegates other than `metro-ai-apps-recipe` live in
  `open-edge-platform/skills`.
- Keep the catalog in [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md)
  in sync with the upstream `skills-config.json` — see
  [`references/DISCOVERY.md`](references/DISCOVERY.md).
