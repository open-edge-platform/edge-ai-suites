# Developer — specify the technical axes (OVMS+FFmpeg microservice, AUTO HW)

Shows the questionnaire when the user **speaks technology** and sets the optional
axes directly. Any axis can still be `auto` — here hardware and the model are
deferred.

**User (technical):**
> I want an OVMS + FFmpeg microservice that runs vehicle detection on an RTSP
> feed. I don't care which device — pick the best Intel one — and suggest a fast
> model for me.

**Orchestrator (Step 1 — one questionnaire, batched, distinct questions):**
1. Outcome — detect vehicles on a live feed and expose results via a service? [yes]
2. Inputs — the RTSP camera URL you'll provide? [RTSP]
3. Camera coverage — one camera / one view? [one camera]
4. Packaging — `microservice` (you asked for a service). [microservice]
5. Deployment — single-host Docker Compose, or Kubernetes? [Docker Compose]
6. Target hardware — `auto` (you deferred → I pick the Intel CPU/GPU/NPU). [auto]
7. Scale — one stream, API access (no dashboard required)? [one stream, API]
8. API recipe — **OVMS + FFmpeg** (as you specified). [ovms-ffmpeg]
9. Models & videos — `auto`: performance goal = low latency → I'll suggest a fast
   detector from the OpenVINO / Intel / Metro Analytics Catalog HF collections. [auto]

**Discovery (Step 2):** API recipe = **OVMS + FFmpeg** takes precedence (see
`references/API_RECIPES.md`) → **OVMS model-serving path** (OVMS + FFmpeg glue
code), **not** `metro-ai-apps-recipe`. Supporting: **`model-download-user`** for
an OVMS-ready IR.

**Resolved axes (Step 3 — decisions for deferred axes, choices for specified):**
- Packaging: `microservice` *(user)*; API recipe: `ovms-ffmpeg` *(user)*.
- Target HW: `AUTO` → **Intel GPU** *(inferred: continuous RTSP, low-latency goal;
  falls back to CPU if no GPU)*.
- Model: `AUTO` → a lightweight YOLO-family vehicle detector from the OpenVINO HF
  collection *(inferred from the low-latency goal)*, fetched as OVMS-ready IR.

**Plan (Step 4 — presented, awaits confirmation):**
- Deliverable: an OVMS service serving the vehicle detector + a small FFmpeg-based
  client that decodes the RTSP feed and calls the OVMS API; results over the
  service API.
- Skills: `model-download-user` (OVMS-ready IR) → OVMS + FFmpeg custom-code path.
- Requirements: Docker + Compose v2; an Intel GPU (render/video groups) for the
  AUTO→GPU choice, else CPU; the RTSP URL.

**Build (Step 5, after "go"):** run `model-download-user` for the OVMS-ready IR,
stand up OVMS, generate the FFmpeg client, then verify the service answers a
sample request. Report the endpoint and how to call it.
