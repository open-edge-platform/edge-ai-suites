# Skill catalog — business objective → open-edge-platform skill

Curated routing table for the `metro-ai-apps-builder` orchestrator. Map the
user's **business objective** (Step 1 answers) to a **primary** skill and any
**supporting** skills, then plan + delegate. Mirror of the upstream
`open-edge-platform/skills` `skills-config.json`;
refresh with [`DISCOVERY.md`](DISCOVERY.md) when it drifts.

> All delegate skills except `metro-ai-apps-recipe` (which lives in this repo)
> are installed from `open-edge-platform/skills` with:
> `npx skills@1.5.23 add open-edge-platform/skills --skill <name>`

## 1. Computer vision — detect / count / track / alert on camera feeds

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| A full **end-to-end analytics stack** (live annotated video + dashboard + alerts) for detection/classification/counting/zone-alerting on any vertical (smart city, retail, industrial, PPE, parking, healthcare…) | **`metro-ai-apps-recipe`** *(this repo)* — production mode (`MODE=production`, the default) | `model-download-user` (custom IR), `dlstreamer-coding-agent` (custom pipeline JSON) |
| A **quick local demo / PoC** — a single lightweight app (no full stack) that just proves a model runs and emits inference: a simple DL Streamer pipeline **or** a minimal OpenVINO inference script | **`metro-ai-apps-recipe`** *(this repo)* — demo/PoC mode (`MODE=demo`) | `dlstreamer-coding-agent` (DL Streamer sub-path), OpenVINO 2026 docs (OpenVINO sub-path), `model-download-user` (model IR) |
| **Multi-camera / spatial** cross-camera tracking & scene fusion (smart-intersection style) | **`scenescape-setup`** — reached via the `metro-ai-apps-recipe` Scenescape opt-in path | `metro-ai-apps-recipe` for the detection front-end |
| A **custom vision pipeline / sample app in code** (Python/C/C++/GStreamer): detection, classification, tracking, VLM, recording, custom elements | **`dlstreamer-coding-agent`** | `model-download-user` |
| **Migrate / convert / port** an existing **NVIDIA DeepStream** (or raw GStreamer) pipeline to an equivalent **Intel DL Streamer** pipeline/app | **`dlstreamer-coding-agent`** | `model-download-user` (equivalent IR model) |

Deliverable shape: *end-to-end solution* (Compose stack) for
`metro-ai-apps-recipe` in **production mode**; *quick single app / PoC* for
`metro-ai-apps-recipe` in **demo mode** (`MODE=demo`) or for
`dlstreamer-coding-agent`; *multi-camera solution* for the Scenescape path. Map
the Step 1 **deployment-target** answer to the recipe mode: "quick local
demo/POC" → `MODE=demo`; "Docker Compose end-to-end" → `MODE=production`.

## 2. Conversational AI — chatbot / Q&A / RAG over documents

| If the user wants… | Primary skill | Notes |
|---|---|---|
| A **chatbot / RAG** over their documents on a single host (Docker Compose) with OpenVINO CPU/GPU or Ollama | **`chatqna-docker-deploy`** | Profile selection, env setup, health checks |
| The same **on Kubernetes** (Helm) | **`chatqna-helm-deploy`** | Translates Compose `setup_env.sh` → `values.yaml` |

## 3. Video understanding — search & summarize a video library

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| Deploy the **Video Search & Summarization** app (summary / search / dual / unified) on Docker | **`vss-deploy`** | `vdms-dataprep-user` (ingest), `multimodal-embedding-serving-user` (embeddings) |
| The same **on Kubernetes** (Helm) | **`vss-deploy-helm`** | — |
| **Search** an indexed library with natural language ("find X", "when did Y happen") | **`vss-search-index`** | requires a search-capable VSS deploy |
| **Summarize** an ingested video | **`vss-summarize-video`** | requires a summary-capable VSS deploy |
| **Ingest** MP4s into a vector DB (VDMS + MinIO) | **`vdms-dataprep-user`** | feeds VSS / retrieval |
| **Embed** text/images/videos for similarity search (CLIP/SigLIP/… 19 models) | **`multimodal-embedding-serving-user`** | building block for retrieval apps |

Typical pipeline: `vdms-dataprep-user` (ingest) → `vss-deploy` (bring up) →
`vss-search-index` / `vss-summarize-video` (use).

## 4. Model preparation

| If the user wants… | Primary skill |
|---|---|
| **Download / convert** a model (HuggingFace, Ollama, Ultralytics, Geti, Pipeline Zoo; INT4/INT8; OVMS-ready IR; healthcare HLS models) | **`model-download-user`** |

Usually a **supporting** step for a deploy/build skill above.

## 5. Model training (computer vision)

| If the user wants… | Primary skill |
|---|---|
| **Discover** available models/recipes/tasks before training | **`getitune-discovering-models`** |
| **Prepare / point datasets** (COCO/YOLO/VOC/Datumaro) | **`getitune-preparing-datasets`** |
| **Train / fine-tune** a classifier/detector/segmentation/keypoint model | **`getitune-training-a-model`** |
| **Export** to OpenVINO IR / ONNX (FP32/FP16) | **`getitune-exporting-a-model`** |
| **Optimize / quantize** to INT8 (NNCF PTQ) | **`getitune-optimizing-a-model`** |
| **Run inference / evaluate** (PyTorch / OpenVINO / ONNX) | **`getitune-running-inference`** |
| Use the **Geti application** end-to-end via REST (project→annotate→train→deploy) | **`geti-using-the-pipeline`** |

Typical training pipeline: `getitune-discovering-models` →
`getitune-preparing-datasets` → `getitune-training-a-model` →
`getitune-exporting-a-model` → `getitune-optimizing-a-model` →
`getitune-running-inference`. The exported/quantized IR can then feed
`metro-ai-apps-recipe` or `dlstreamer-coding-agent` via `model-download-user`.

## 6. Robotics / Physical AI

| If the user wants… | Primary skill |
|---|---|
| **Train** a robot policy (ACT, Pi0, Pi0.5, GR00T, SmolVLA) | **`physicalai-train-training-a-policy`** |
| Work with **datasets** (LeRobot format) | **`physicalai-train-working-with-datasets`** |
| **Add / modify** a policy family | **`physicalai-train-adding-a-policy`** |
| **Benchmark** a policy in simulation | **`physicalai-train-benchmarking-a-policy`** |
| **Export / validate** a policy (ONNX/OpenVINO/Torch/ExecuTorch) | **`physicalai-train-exporting-and-validating`** |
| **Load** an exported policy for runtime | **`physicalai-runtime-loading-exported-policies`** |
| **Run** a policy on a robot | **`physicalai-runtime-running-policy-on-robot`** |
| Configure the **inference pipeline** (pre/post-processors) | **`physicalai-runtime-configuring-inference-pipeline`** |
| Add a **camera backend** | **`physicalai-runtime-adding-a-camera-backend`** |
| Add a **robot hardware integration** (SO101, Trossen WidowX) | **`physicalai-runtime-adding-a-robot-integration`** |

Typical robot pipeline: train (`physicalai-train-*`) → export
(`physicalai-train-exporting-and-validating`) → load & run
(`physicalai-runtime-loading-exported-policies` →
`physicalai-runtime-running-policy-on-robot`).

## Routing heuristics

- **Verb + object** in the objective is the strongest signal:
  *detect/count/track + camera* → §1; *ask/answer + documents* → §2;
  *search/summarize + video* → §3; *download/convert + model* → §4;
  *train/fine-tune + dataset* → §5; *run/deploy + robot policy* → §6.
- **Deployment target** picks the Docker vs Helm variant (chatqna, vss) and the
  `metro-ai-apps-recipe` mode: a *quick local demo/POC* → recipe **demo mode**
  (`MODE=demo`, a single DL Streamer or OpenVINO app); a *Docker Compose
  end-to-end* stack → recipe **production mode** (`MODE=production`). Prefer the
  recipe's demo mode over calling `dlstreamer-coding-agent` directly when the
  user came in via a **business objective** (it wraps the same DL Streamer
  hand-off and also offers the OpenVINO path); route straight to
  `dlstreamer-coding-agent` only when the user explicitly wants to author custom
  pipeline **code**.
- **"Custom model"** almost always adds `model-download-user` as a supporting
  step before a deploy/build skill.
- **Migrate / convert / port** verbs against **NVIDIA DeepStream** (or raw
  GStreamer) → **`dlstreamer-coding-agent`**: the user has an existing DeepStream
  pipeline and wants the equivalent **Intel DL Streamer** code. Add
  `model-download-user` when the NVIDIA model needs an OpenVINO IR equivalent.
- When two domains appear (e.g. *train then deploy*), sequence the skills and
  confirm the **whole pipeline** once in the plan.
- If no row matches, do **not** invent a skill — say so and offer the closest
  entry or a custom-code path.
