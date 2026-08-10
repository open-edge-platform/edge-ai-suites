# Prompt Library

Reusable business-objective prompts in YAML format. Each prompt is **as simple as
possible — it states only a business objective** (e.g. "I want to detect people
in my camera feeds") and hands off to the
[`metro-ai-apps-builder`](.github/skills/metro-ai-apps-builder/SKILL.md)
orchestrator skill. The prompts carry **no technology and no parameters** — the
skill owns all of that.

## The orchestrator: `metro-ai-apps-builder`

`metro-ai-apps-builder` **owns the conversation**. It turns a plain business
outcome into a running Intel Edge AI application by:

- Running a **business-objective Q&A** — it asks what you want to achieve, your
  inputs, where it runs, and your hardware, **not** which technology to use. You
  are never asked to choose a framework, model, precision, or device.
- **Discovering the relevant skill(s)** from the
  [open-edge-platform/skills](https://github.com/open-edge-platform/skills)
  catalog — vision analytics, multi-camera scene analysis, conversational
  Q&A/RAG, video search & summarization, multimodal embeddings, model
  download/convert, model training, or robotics — using a curated routing table
  ([`references/SKILL_CATALOG.md`](.github/skills/metro-ai-apps-builder/references/SKILL_CATALOG.md))
  plus live discovery
  ([`references/DISCOVERY.md`](.github/skills/metro-ai-apps-builder/references/DISCOVERY.md)).
- **Inferring all technology** (framework, model, precision, device, deployment
  mode) from your business answers and the target skill's parameters.
- **Presenting a plan and waiting for your confirmation** — it summarises the
  deliverable, which skill(s) will build it, and the inferred technology, and
  only starts building **after you approve**. Nothing is created before then.
- **Building by delegating** to the chosen skill(s) — it does not re-implement
  their work. For a computer-vision analytics stack it delegates to the
  [`metro-ai-apps-recipe`](.github/skills/metro-ai-apps-recipe/SKILL.md) skill in
  this same repository; for every other domain it installs and invokes the
  matching open-edge-platform skill.

## The vision delegate: `metro-ai-apps-recipe`

For camera-feed detection/counting/zone-alerting, the orchestrator hands off to
[`metro-ai-apps-recipe`](.github/skills/metro-ai-apps-recipe/SKILL.md), which
builds a streamlined single-compose vision-analytics stack: DL Streamer Pipeline
Server + MediaMTX/WebRTC + Coturn + Mosquitto + Node-RED + Grafana + Nginx TLS
reverse proxy (live annotated video reaches Grafana over **WebRTC**, embedded in
`<iframe>` panels; no Prometheus, no OpenTelemetry). It has an **opt-in
multi-camera SceneScape** spatial-analysis path (smart-intersection style) that
delegates to the external
[`scenescape-setup`](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup)
skill.

The solution architecture is inspired by the open-edge-platform
[Metro Vision AI App Recipe](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe).

```
prompt-library/
├── .github/skills/
│   ├── metro-ai-apps-builder/             # orchestrator: Q&A + skill discovery + plan + delegate
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── SKILL_CATALOG.md           # business objective → open-edge-platform skill
│   │   │   └── DISCOVERY.md               # live discovery + `npx skills add`
│   │   ├── example-prompts/               # multi-domain walk-throughs
│   │   └── evals/evals.json
│   └── metro-ai-apps-recipe/              # vision delegate: end-to-end DLSPS + WebRTC stack
│       ├── SKILL.md
│       └── references/                    # pipeline, proxy/UI, node-red, install, tests, scenescape
└── prompts/
    ├── object-detection.yaml              # one minimal business-objective prompt per use-case
    ├── person-detection.yaml
    ├── vehicle-detection.yaml
    ├── unauthorized-access-detection.yaml
    └── worker-safety-compliance.yaml
```

## Prompt file schema

Every `*.yaml` under `prompts/` uses the following fields:

| Field | Type | Purpose |
|---|---|---|
| `name` | string | Unique kebab-case identifier |
| `description` | string | One-paragraph summary of the business objective it addresses |
| `prompt` | string (block scalar `\|`) | A minimal business-objective statement + hand-off to the skill (no technology, no parameters) |
| `tags` | list[string] | Discovery / filtering keywords (vertical, deliverable, hardware) |

## How to use

Point Copilot at the prompt matching the **outcome you want** (e.g.
"detect people", "count vehicles", "flag PPE violations"), or just state your
objective in your own words. The `metro-ai-apps-builder` orchestrator takes over:
it asks a few **business** questions, discovers the right open-edge-platform
skill(s) for your objective, presents a plan and inferred technology, and — only
after you confirm — builds the deliverable by delegating to those skill(s).

## Adding a new use-case

The orchestrator is **domain-agnostic** and the vision delegate
(`metro-ai-apps-recipe`) is **vertical-agnostic** — the same architecture serves
any DL Streamer / OpenVINO pipeline (PPE compliance, ANPR, retail queue, defect
detection, fall detection, livestock counting, etc.; see the vertical matrix in
[`.github/skills/metro-ai-apps-recipe/SKILL.md`](.github/skills/metro-ai-apps-recipe/SKILL.md)).

To add a new **vision** use-case, just drop a minimal `.yaml` file under
`prompts/` that states only the business objective and hands off to the
orchestrator (copy an existing one and change the objective wording). The
orchestrator infers the object/model/rule/topics and delegates to
`metro-ai-apps-recipe` — no per-use-case config file is required.

To route a **new domain** (e.g. a new open-edge-platform skill), add a row to the
orchestrator's routing table in
[`.github/skills/metro-ai-apps-builder/references/SKILL_CATALOG.md`](.github/skills/metro-ai-apps-builder/references/SKILL_CATALOG.md)
mapping the business objective to that skill. See
[`references/DISCOVERY.md`](.github/skills/metro-ai-apps-builder/references/DISCOVERY.md)
for keeping the catalog in sync with upstream `skills-config.json`.
