# Skill catalog — manufacturing business objective → skill

Curated routing table for the `manufacturing-ai-app-builder` orchestrator.
Map the user's **business objective** (Step 1 answers, especially "what feeds
the decision") to a **primary** skill and any **supporting** skills, then plan
+ delegate.

> `manufacturing-timeseries-app-recipe` and `manufacturing-multimodal-app-recipe`
> ship in **this workspace** under `.agents/skills/` — no install needed.
> `metro-ai-app-recipe`, `dlsps-user`, `dlstreamer-coding-agent`, and
> `time-series-analytics-user` also ship locally here; if a target
> environment lacks one, see [`DISCOVERY.md`](DISCOVERY.md) for the fetch path
> (`npx skills@1.5.23 add open-edge-platform/skills --skill <name>`, or
> `open-edge-platform/dlstreamer` for `dlstreamer-coding-agent`).

## 1. Vision + sensor fusion — one correlated verdict from both a camera and a sensor

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| A defect/anomaly verdict that must **combine** a camera-side defect signal **and** a sensor-side anomaly signal (AND/OR logic, timestamp-correlated) — e.g. weld quality (vision + pressure/gas/current), machining (surface defect + vibration), PCB (visual + electrical test) | **`manufacturing-multimodal-app-recipe`** | `dlsps-user` (vision pipeline ops), `time-series-analytics-user` (sensor UDF pattern), `model-download-user` (custom vision IR) |

Deliverable shape: end-to-end Compose stack (DLSPS + Telegraf/InfluxDB + Time
Series Analytics + Fusion Analytics + Grafana + Nginx). Route here **only**
when both signals must be correlated into **one** decision — if the user
merely has both a camera and a sensor but only cares about one of them, route
to §2 or §3 instead.

## 2. Time series only — sensor/OPC-UA/MQTT anomaly detection, no camera

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| A **full deployable app** for a new sensor-monitoring vertical — simulator or real OPC-UA/MQTT ingest, Kapacitor UDF, MQTT/OPC-UA alerting, Grafana dashboard, registered as a new `apps/<name>/` sample app | **`manufacturing-timeseries-app-recipe`** | `time-series-analytics-user` (the UDF/TICKscript pattern itself) |
| Just a **UDF + TICKscript** deployed onto an **already-running** Time Series Analytics Microservice — no simulator, no Grafana, no app registry | **`time-series-analytics-user`** | — |

Deliverable shape: end-to-end Compose stack + new `apps/<name>/` folder for
the first row; a deployed UDF package for the second. The Step 1 "full
stack vs quick prototype" answer picks between these two rows.

## 3. Vision only — camera-based inspection/detection, no sensor correlation

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| A **full end-to-end analytics stack** (live annotated video + dashboard + alerts) for detection/classification/counting/zone-alerting on any vertical, including manufacturing (defect detection, PPE compliance, zone intrusion, forklift tracking) | **`metro-ai-app-recipe`** — production mode (`MODE=production`, the default) | `model-download-user` (custom IR), `dlstreamer-coding-agent` (custom pipeline JSON) |
| A **quick local demo / PoC** — a single lightweight app (no full stack) proving a model runs: a simple DL Streamer pipeline **or** a minimal OpenVINO inference script | **`metro-ai-app-recipe`** — demo/PoC mode (`MODE=demo`) | `dlstreamer-coding-agent` (DL Streamer sub-path), `model-download-user` (model IR) |
| **Multi-camera / spatial** cross-camera tracking & scene fusion | **`scenescape-setup`** — reached via the `metro-ai-app-recipe` Scenescape opt-in path | `metro-ai-app-recipe` for the detection front-end |
| A **custom vision pipeline / sample app in code** (Python/C/C++/GStreamer), or **migrating** an NVIDIA DeepStream pipeline to Intel DL Streamer | **`dlstreamer-coding-agent`** | `model-download-user` |
| Just **deploy/operate** the DL Streamer Pipeline Server via REST — start/stop/monitor pipelines, configure `config.json`, no dashboard/alerting stack | **`dlsps-user`** | — |

Deliverable shape: end-to-end Compose stack for `metro-ai-app-recipe`
production mode; quick single app for demo mode or `dlstreamer-coding-agent`;
a running/operable pipeline-server container for `dlsps-user` with no
Grafana/MQTT/dashboard layer.

## Routing heuristics

- **The single strongest signal is "what feeds the decision?" (Step 1, Q2).**
  Camera + sensor **both required to agree/combine** → §1. Sensor only → §2.
  Camera only → §3. Get this answer unambiguous before mapping further — it
  picks the entire primary-skill family, not just a parameter.
- **"Full stack" vs "just the building block"** is the second-strongest
  signal within §2 and §3: a dashboard + alerting + simulator scaffold routes
  to the recipe skill (`manufacturing-timeseries-app-recipe` /
  `metro-ai-app-recipe`); a bare UDF or bare pipeline-server operation routes
  to the underlying microservice-user skill (`time-series-analytics-user` /
  `dlsps-user`).
- **Don't over-route to fusion.** Fusion (§1) is for when one verdict must
  come from **both** modalities together (AND/OR logic). If the user has a
  camera and a sensor but the decision only genuinely depends on one of them,
  route single-modality (§2 or §3) — adding an unused modality is
  over-engineering, not fidelity to the objective.
- **"Custom model"** almost always adds `model-download-user` as a supporting
  step before a build skill in any section.
- **Migrate / convert / port** verbs against NVIDIA DeepStream (or raw
  GStreamer) → **`dlstreamer-coding-agent`** (§3), same as the general
  `metro-ai-app-builder` catalog.
- **Multi-camera spatial correlation with no sensor** is NOT time-series
  fusion — it's `scenescape-setup` via `metro-ai-app-recipe` (§3), not
  `manufacturing-multimodal-app-recipe` (§1), because there's no sensor
  stream to correlate against.
- When the objective spans two skills (e.g. prototype a UDF now, scaffold the
  full app later), sequence them and confirm the **whole pipeline** once.
- If no row matches, do **not** invent a skill — say so and offer the closest
  entry or a custom-code path.
