# Surgical Instrument Sample App

Real-time polyp detection on endoscopic video using Intel hardware acceleration (CPU / Intel Arc iGPU / Intel NPU) via DL Streamer.

> **⚠️ Not for clinical use.** This is a developer reference implementation for evaluating Intel inference performance on edge hardware. It is **not** a medical device and must not be used for diagnosis, treatment, or any patient-care decision.

## At a glance

| | |
|---|---|
| **Model** | YOLO11n (FP16 OpenVINO IR) — trained in-container on CVC-ColonDB (mAP@50 ≈ 0.98 on val) |
| **Inference** | Ultralytics (train/export) + OpenVINO 2026.2 (serve) on Intel Arc iGPU via torch+xpu |
| **Backend** | Flask 3.0 — bootstrap orchestrator + REST + SSE + MJPEG streaming (`backend/main_server.py`) |
| **UI** | React + Vite + nginx |
| **Target latency** | < 30 ms end-to-end at 1080p (validated: ~23 ms mean, ~28 ms p99 on Arc iGPU) |
| **First-boot time** | 20–35 min while YOLO11n trains on the iGPU (subsequent boots: seconds — IR is cached) |

## What the UI shows

Open http://localhost:8080 (or the LAN URL printed by `make up`/`make run`). After clicking **Start** the left panel begins streaming inference frames and the right column exposes the KPIs a reviewer typically asks for:

- **Video feed** — 1080p H.264 loop with per-frame polyp bounding boxes.
- **Detection Status card** (hero, under the video)
  - Live pill: `DETECTED` / `NOT DETECTED` + confidence
  - `SESSION` sub-bar: cumulative polyp instances, % of frames with a detection, positive-frame count
- **Pipeline Performance table** — `Workload | Model | Device | FPS | E2E mean | E2E P90 | E2E P95 | Status`. `E2E mean` is the end-to-end frame residence mean over the rolling recent-frame window; `E2E P90` and `E2E P95` are nearest-rank percentiles over the same window.
- **Model & Input block** — model name, precision (`FP16 OpenVINO IR`), task/dataset, video source resolution, model input tensor size, target device (`GPU` / `CPU` / `NPU`).
- **Platform accordion** — CPU / GPU / NPU utilization from `intel-npu-info` + `nvidia-smi`-style samplers.

All of the above is driven by a single Server-Sent Events stream at `/api/events` (~1 Hz snapshot) and an MJPEG stream at `/api/video_feed`, both proxied through nginx with `proxy_buffering off`.

## Topology

Two services on a private Docker bridge. Only the UI (:8080) is published to the host — the backend is reachable only through the UI's nginx reverse-proxy.

```
HOST :8080 ─→ surgical-ui        (nginx + React SPA + /api reverse-proxy)
            INTERNAL surgical-internal bridge
                └─ surgical-backend   Flask 3.0
                                      · bootstrap: fetch → train → export IR
                                      · serve:     REST + SSE + MJPEG on :5001
                                      · devices:   /dev/dri (Intel Arc iGPU)
```

The UI does **not** unblock until `surgical-backend` reports `/api/readiness → ready`. On first boot this includes the full train pipeline; the browser tab simply won't answer until the model is trained and served. This is the "gate UI on BE ready" contract — no user-visible bootstrap UX.

## Quickstart (Docker)

The repo does not ship the medical dataset, trained model binaries, or demo videos. Prepare them locally first, then start the stack. This keeps the demo reproducible without any dependency on a private PTL/Bangalore machine.

> **Behind a corporate proxy?** Read [0. Corporate proxy setup](#0-corporate-proxy-setup) first. Both the image build and the runtime `yolo11n.pt` download need proxy settings, otherwise `make up` will fail with a curl timeout during bootstrap.

### 0. Corporate proxy setup

Two equivalent ways to inject proxy settings — pick one:

**Option A (recommended, persistent):** copy `.env.example` to `.env` and edit it. `docker compose` auto-loads `.env` in this directory for variable interpolation, so `make up` picks the values up without needing them exported in your shell.

```bash
cp .env.example .env
# then edit .env and uncomment / set HTTP_PROXY, HTTPS_PROXY, NO_PROXY.
```

**Option B (ad-hoc):** export the standard proxy env vars in the shell you run `make` from **before** `make up`.

```bash
export HTTP_PROXY=http://proxy.your-corp.com:912
export HTTPS_PROXY=http://proxy.your-corp.com:912
export NO_PROXY=localhost,127.0.0.1,.your-corp.com,surgical-mqtt,surgical-pipeline,surgical-backend,surgical-ui
```

Either way `docker-compose.yaml` forwards the values to `docker build` (as build args) and to the running containers (as env vars), so `apt`, `pip`, `wget`, `curl`, and Ultralytics all honour them. `make up` runs a preflight check and warns if you appear to be on an Intel corp network but neither `.env` nor exported vars provide a proxy.

Notes:
- Include the internal service names in `NO_PROXY` so container-to-container traffic (backend → pipeline, backend → mqtt) is not routed through the proxy.
- Docker daemon also needs a proxy config to `pull` the base image. If `docker pull ubuntu:24.04` works, you're fine. Otherwise configure `~/.docker/config.json` or `/etc/systemd/system/docker.service.d/http-proxy.conf` per your IT policy.
- Verify from the shell before building:

  ```bash
  curl -sS -o /dev/null -w "%{http_code}\n" https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
  # expect: 200 or 302
  ```

If GitHub is fully blocked even with the proxy, use the offline weights workaround in [step 2.1](#21-optional-pre-place-yolo11npt-if-github-is-blocked).

### 1. Download the dataset

- Preferred (working): **CVC-ColonDB mirror on Kaggle** — https://www.kaggle.com/datasets/longvil/cvc-colondb (same 380-image set + masks; direct `kaggle datasets download longvil/cvc-colondb` works with a personal Kaggle API token).
- Do not add the dataset to git; it stays local under `datasets/`.
- Place the archive or extracted contents here (create the folder if it doesn't exist):

  ```text
  Surgical_Instrument/datasets/CVC-ColonDB/raw/
  ```

- Accepted archive types: `.zip`, `.tar`, `.tar.gz`, `.tgz`. Extract `.rar` downloads locally before copying.

### 2. Train and export the model

The user only needs to download and place the dataset. After that, the repo script can download the YOLO11n base model, train it, export it, and cache the final OpenVINO IR.

Model source:

- YOLO11n model family: https://docs.ultralytics.com/models/yolo11/
- Ultralytics model download/reference: https://docs.ultralytics.com/tasks/detect/
- Base weights direct URL: https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt (~5.4 MB, downloaded automatically by Ultralytics during `make backend-bootstrap`)

**Expected flow: train from this repo**

```bash
make backend-venv       # one-time Python environment with torch+xpu, Ultralytics, OpenVINO
make backend-bootstrap  # prepares CVC-ColonDB, trains YOLO11n, exports FP16 OpenVINO IR
```

`backend-bootstrap` does the full model preparation:

- reads the dataset from `datasets/CVC-ColonDB/raw/`
- extracts the archive if needed
- converts CVC masks into YOLO bounding-box labels
- creates the train/validation/test split
- downloads the base `yolo11n.pt` weights through Ultralytics
- trains YOLO11n using the settings in `backend/config/model.yaml`
- exports the best checkpoint to FP16 OpenVINO IR
- writes the `.trained_ok` cache marker

Expected output after training:

```text
models/yolo11n_polyp/
├── .trained_ok
└── best_openvino_model/
    ├── best.xml
    ├── best.bin
    └── metadata.yaml
```

#### 2.1. (Optional) Pre-place `yolo11n.pt` if GitHub is blocked

If the runtime download of `yolo11n.pt` fails with a curl timeout (return value 28), pre-download the weights on any machine with GitHub access and place the file inside the `surgical-cache` volume so the bootstrap skips the network fetch:

```bash
# On a machine that can reach GitHub:
curl -L -o yolo11n.pt \
  https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt

# Copy to the target host, then place it in the backend cache volume.
# `make up` must have created the container at least once for this to work:
docker cp yolo11n.pt surgical-backend:/cache/weights/yolo11n.pt

# Restart the backend so the bootstrap picks up the cached weights.
docker restart surgical-backend
```

The bootstrap looks for `${CACHE_DIR}/weights/<model_name>.pt` (default: `/cache/weights/yolo11n.pt`) before falling back to Ultralytics' auto-download.

**Optional: train elsewhere and copy the result**

- Train YOLO11n on CVC-ColonDB on another machine.
- Export the trained model to FP16 OpenVINO IR. For an Ultralytics checkpoint, the export command is typically:

  ```bash
  yolo export model=/path/to/best.pt format=openvino half=True imgsz=640
  ```

- Copy the final files into this exact layout:

  ```text
  Surgical_Instrument/models/yolo11n_polyp/
  ├── .trained_ok
  └── best_openvino_model/
      ├── best.xml
      ├── best.bin
      └── metadata.yaml
  ```

- `best.xml` and `best.bin` are required. `metadata.yaml` is recommended because DL Streamer/OpenVINO can use the exported Ultralytics metadata.
- `.trained_ok` is the cache marker checked by `make up` and the backend. If you trained outside this repo, create the marker after copying the IR:

  ```bash
  mkdir -p models/yolo11n_polyp/best_openvino_model
  date -Is > models/yolo11n_polyp/.trained_ok
  ```

### 3. Generate the demo video (required)

- Fresh clones do not have `videos/polyp_test.mp4`; generate it before `make doctor` / `make up`.
- Run:

  ```bash
  .venv-backend/bin/python scripts/create_endoscopy_video.py \
    --images-dir datasets/CVC-ColonDB/raw/images \
    --output videos/polyp_test.mp4 \
    --seconds 60 --fps 60 --width 1920 --height 1080
  ```

  This creates/overwrites `videos/polyp_test.mp4` using an H.264-compatible codec for the default app file-source pipeline.

### 4. Validate and start

```bash
make doctor          # checks Docker, accelerators, cached IR, videos, and port 8080
make up              # builds images and starts backend + UI (trains if IR is not cached)
make logs            # optional: follow readiness/startup logs
```

When the backend is ready, open:

```text
http://localhost:8080
```

For later runs, use the fast path:

```bash
make run
```

`make run` requires the cached IR and `.trained_ok` marker. If they are missing, it stops and tells the user to prepare or seed the model first.

`make up` and `make run` both **auto-detect** any `/dev/video*` devices on
the host and layer in a compose override that makes them available to the
pipeline container. The UI's Settings modal is the primary runtime picker for
choosing between the recorded video and any attached camera — see [Runtime
configuration](#runtime-configuration) below.

## Runtime configuration

Everything reconfigurable at runtime lives in the **Settings** modal —
opened via the `⚙ Settings` button in the top action bar, next to Start/Stop.

**First launch.** The app opens with a one-time **research-use disclaimer**
that must be acknowledged before the main UI is interactive. The ack is
stored in `localStorage` under `surgical_disclaimer_ack_v1` and does not
survive a browser-profile wipe.

### Input Source tab

Pick where frames come from without editing config files or restarting
compose. Three source kinds are supported; kinds with no detected devices
are visible but disabled so it's obvious what the app supports.

| Kind | Argument | Populated by |
|---|---|---|
| **Video file** | basename under `./videos/` | `GET /api/videos` — lists everything with `.mp4 .mkv .avi .mov .ts` |
| **USB / v4l2 camera** | `/dev/videoN` | `GET /api/devices/cameras` — reads `/sys/class/video4linux` |
| **Basler camera** | serial number | `GET /api/devices/cameras` — pypylon enumeration (ships in Slice E) |

- **Upload** a new video with the "Choose file…" button (max 500 MB, extension whitelist enforced server-side). New uploads land in the same `./videos/` volume and appear in the dropdown immediately.
- **Apply** persists the selection client-side. It takes effect on the **next** Start — the pipeline rejects source changes mid-stream. If a pipeline is running, the modal shows a banner and blocks changes until you Stop.
- **Cameras** are compose-time devices. Hot-plugging after `make up` requires
  `make run` (or the equivalent `docker compose up -d`) so the container can
  see the new node — the UI's picker only surfaces what's already mounted.

### Devices tab

Single-row table (`Workload · Model · Device`) with a dropdown for the
polyp-detection accelerator: `CPU`, `GPU` (Intel Arc iGPU — recommended),
`NPU` (Intel AI Boost). Save applies the change on the next Start; Reset
session clears the last inference session's aggregates without stopping the
backend process.

### Backend contract (for scripting / smoke tests)

The UI is a thin wrapper over these endpoints, so any of them can be driven
from `curl` for automation.

| Endpoint | Purpose |
|---|---|
| `GET /api/videos` | List `{name, size_bytes, mtime}` under `VIDEOS_DIR` (default `/videos`) |
| `POST /api/videos` | Multipart upload (`file` field). `415` for wrong ext, `409` for duplicate, `413` for oversize |
| `GET /api/devices/cameras` | `{v4l2:[…], basler:[…], basler_note?}` |
| `GET /api/config` | Reflects live source: `{video_file, default_video, source:{kind,arg}, devices:{detect}}` |
| `POST /api/start` | Optional body: `{device?, source?:{kind,arg}}` — persisted to `ServerState` for subsequent Starts |
| `POST /api/stop` · `POST /api/reset` | Lifecycle |
| `POST /api/device` | Set active accelerator for the polyp-detection workload |

### Pre-flight: `make doctor`

Read-only diagnostic that checks the host before you run `make up`. Reports
each item as `[ OK ]`, `[WARN]`, or `[FAIL]`; exits non-zero only on genuine
fatals (missing Docker, no video assets, port collision with a foreign
process). Own-stack aware — if `surgical-ui` is already running on
`UI_HOST_PORT`, that's reported as OK, not as a conflict.

Sections: host prerequisites · accelerator visibility · cameras · assets ·
port availability · compose config. Sample output:

```
[doctor] --- accelerator visibility ---
  [ OK ] /dev/dri present (renderD* count: 1)
  [ OK ] /dev/accel/accel0 present (NPU visible)
[doctor] --- assets ---
  [ OK ] cached IR : models/yolo11n_polyp/best_openvino_model (5.4M)
  [ OK ] 2 demo video(s) under ./videos/
[doctor] --- port availability ---
  [ OK ] port 8080 free
[doctor] all critical checks passed — 'make up' should succeed.
```

## Repo layout (short)

```
Surgical_Instrument/
├── backend/
│   ├── main_server.py         # bootstrap FSM entrypoint
│   ├── pipeline/inference.py  # OpenVINO inference worker + rolling p99 stats
│   └── server/app.py          # Flask REST + SSE snapshot builder
├── ui/
│   └── src/
│       ├── components/DetectionPanel/   # video + hero detection card
│       ├── components/RightPanel/       # Pipeline Performance + Model & Input + Platform accordions
│       ├── redux/slices/detectionSlice.ts
│       ├── redux/middleware/sseMiddleware.ts
│       └── types/detection.ts
├── scripts/
│   └── create_endoscopy_video.py  # generate H.264 demo video from CVC-ColonDB frames
├── docker-compose.yaml
└── Makefile                   # up / run / down / logs / clean
```

