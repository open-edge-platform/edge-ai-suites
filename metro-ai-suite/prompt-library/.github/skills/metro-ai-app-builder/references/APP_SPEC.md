<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# App spec — the four optional technical axes

The `metro-ai-app-builder` questionnaire (Step 1) asks one outcome-focused set of
questions **plus** four **optional, technical axes**. Each axis is its own
distinct question; each accepts either an explicit value **or** `auto` (defer —
you decide from the other answers + the catalog). This file defines the
vocabularies, the `auto` semantics, and how each axis feeds routing (Step 2) and
the delegate hand-off (Steps 3–5).

> Load this when the user gives — or you need to infer — any technical axis.
> Prompts in `prompts/*.yaml` remain business-only; these axes live here and in
> the skill body, never in a prompt.

## Axis 1 — Packaging type (Q4)

What shape should the deliverable take?

| Value | Meaning | Typical route |
|---|---|---|
| `demo` / `poc` | A single lightweight app that proves a model runs and emits results — no full stack. | `dlstreamer-coding-agent` (vision); OpenVINO custom app for OV+OpenCV. |
| `microservice` | A running REST/streaming service — e.g. the full end-to-end analytics stack (DLSPS + dashboards + alerts). | `metro-ai-apps-recipe` (vision stack); the relevant deploy skill for other domains. |
| `function` | A single batch / one-shot job (process a file/folder, emit a result, exit). | `dlstreamer-coding-agent` or an OpenVINO/OVMS custom job. |
| `port` | Migrate/convert an existing app or pipeline to the Intel stack. | `dlstreamer-coding-agent` (e.g. DeepStream → DL Streamer). |
| `auto` *(default)* | You pick the packaging from the outcome, camera coverage, and scale answers. | — |

## Axis 2 — API recipe (Q8)

Which media + analytics API stack? **This is a routing answer** — it selects the
delegate skill / code path. See [`API_RECIPES.md`](API_RECIPES.md) for the full
per-recipe detail. Summary:

| Value | Routes to |
|---|---|
| `dls` / `dl-streamer` | **`dlstreamer-coding-agent`** (the DLS skill) — **not** `metro-ai-apps-recipe`. |
| `ov-opencv` | OpenVINO + OpenCV custom-code path (per OpenVINO docs) + `model-download-user`. |
| `ovms-ffmpeg` | OVMS model-serving + FFmpeg glue + `model-download-user` (OVMS-ready IR). |
| `auto` *(default)* | You pick the recipe from packaging + outcome. |

> The full end-to-end analytics **stack** (`metro-ai-apps-recipe`) is chosen by
> the **packaging** axis (`microservice`), *not* by picking the DL Streamer API
> recipe. A user who asks for "a DL Streamer pipeline/app" wants
> `dlstreamer-coding-agent`.

## Axis 3 — Target hardware (Q6)

Which Intel device runs inference?

| Value | Meaning |
|---|---|
| `cpu` | Intel CPU. |
| `gpu` | Intel GPU (requires `video`/`render` groups on the host). |
| `npu` | Intel NPU. |
| `auto` *(default)* | You pick the Intel device (`CPU`/`GPU`/`NPU`) from the workload and scale. |

Notes:

- Use only **CPU / GPU / NPU** — do **not** name platforms or generations.
- You **may** surface multi-vendor alternatives as *suggestions only*; the built
  deliverable targets Intel.

## Axis 4 — Models & videos (Q9)

A specific model and/or video source, or `auto`.

- **Explicit** — the user names a model (and/or a video/RTSP/file source); carry
  it straight through to the delegate.
- **`auto` (default)** — ask for (or infer) a **performance goal** (accuracy vs
  latency vs footprint) and suggest a model from the relevant Hugging Face
  collections, then confirm in the plan:
  - **OpenVINO** collection — OpenVINO-optimized / IR-ready models.
  - **Intel** collection — Intel-published models.
  - **Metro Analytics Catalog** — metro/vision analytics models curated for these
    use cases.
- When a specific IR is needed for a delegate, add `model-download-user` as a
  supporting step to fetch/convert it.

## Putting it together

1. Ask the axes as **distinct** questions (Step 1); accept `auto` on any.
2. Resolve every `auto` axis from the other answers + the catalog.
3. Let **API recipe** (then packaging) drive the primary delegate (Step 2 /
   [`API_RECIPES.md`](API_RECIPES.md)); map **target HW** and **models & videos**
   to the delegate's parameters (device, model, source).
4. Show the resolved axes in the Step 4 plan as decisions (for `auto`) or as the
   user's choices (for explicit answers), then delegate.
