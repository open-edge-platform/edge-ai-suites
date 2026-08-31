# Surgical Instrument Sample App

> ⚠️ This application is for **reference and evaluation purposes**. It is
  **not intended for direct use in clinical or diagnostic environments** and is not
  validated for such a purpose.

Real-time polyp detection in endoscopic video using Intel hardware acceleration
(CPU / Intel Arc iGPU / Intel NPU) via DL Streamer.

|   |   |
|---|---|
| **Model** | YOLO11n (FP16 OpenVINO IR) — trained in-container on ColonDB (mAP@50 ≈ 0.98 on val) |
| **Inference** | Ultralytics (train/export) + OpenVINO 2026.2 (serve) on Intel Arc iGPU via torch+xpu |
| **Backend** | Flask 3.0 — bootstrap orchestrator + REST + SSE control plane (`backend/main_server.py`) |
| **UI** | React + Vite + nginx |
| **Target latency** | < 30 ms end-to-end at 1080p (validated: ~23 ms mean, ~28 ms p99 on Arc iGPU) |
| **First-boot time** | 20–35 min while YOLO11n trains on the iGPU (subsequent boots: seconds — IR is cached) |


## Topology

Three services on a private Docker bridge. Only the UI (:8080) is published to the
host — backend and pipeline are internal.

```
HOST :8080 ─→ surgical-ui        (nginx + React SPA + /api reverse-proxy)
      INTERNAL surgical-internal bridge
        ├─ surgical-backend   Flask 3.0 control plane + SSE on :5001
        │                     · bootstrap: fetch → train → export IR
        │                     · runtime:   start/stop + health/latency fanout
        └─ surgical-pipeline  GStreamer + DL Streamer on :8091
                    · sources:   file | basler
                    · latency:   GST latency tracer (/latency)
```

The UI does **not** unblock until `surgical-backend` reports `/api/readiness → ready`.
On the first boot this includes the full train pipeline; the browser tab simply will not answer
until the model is trained and served. This is the "gate UI on BE ready" contract —
no user-visible bootstrap UX.


## User Interface

Open http://localhost:8080 (or the LAN URL printed by `make up`/`make run`) and click
**Start** in the left configuration panel. The right column exposes typical KPIs:

- **Config panel (left accordion)** — source selection (`file` or `basler`), source argument (video path / camera serial), device choice, and Start/Stop/Reset controls.
- **Pipeline Performance table** — `Workload | Model | Device | FPS | Mean | P50 | P90 | P95 | P99 | Status`. Percentiles are computed from the pipeline latency tracer rolling window.
- **Model & Input block** — model name, precision (`FP16 OpenVINO IR`), task/dataset, video source resolution, model input tensor size, target device (`GPU` / `CPU` / `NPU`).
- **Platform accordion** — CPU / GPU / NPU utilization from `intel-npu-info` + `nvidia-smi`-style samplers.

For more details, see the [User Interface document](./docs/user-guide/user-interface.md).







## Quickstart (Docker)

The repo does not ship the medical dataset, trained model binaries, or demo videos.
Prepare them locally first, then start the stack. This keeps the demo reproducible without
any dependency on a private PTL/Bangalore machine.

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
export NO_PROXY=localhost,127.0.0.1,.your-corp.com,surgical-pipeline,surgical-backend,surgical-ui
```

Either way `docker-compose.yaml` forwards the values to `docker build` (as build args) and to the running containers (as env vars), so `apt`, `pip`, `wget`, `curl`, and Ultralytics all honour them. `make up` runs a preflight check and warns if you appear to be on an Intel corp network but neither `.env` nor exported vars provide a proxy.

Notes:
- Include the internal service names in `NO_PROXY` so container-to-container traffic (backend → pipeline) is not routed through the proxy.
- Docker daemon also needs a proxy config to `pull` the base image. If `docker pull ubuntu:24.04` works, you're fine. Otherwise configure `~/.docker/config.json` or `/etc/systemd/system/docker.service.d/http-proxy.conf` per your IT policy.
- Verify from the shell before building:

  ```bash
  curl -sS -o /dev/null -w "%{http_code}\n" https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
  # expect: 200 or 302
  ```

If GitHub is fully blocked even with the proxy, use the offline weights workaround in [step 2.1](#21-optional-pre-place-yolo11npt-if-github-is-blocked).

### 1. Download the dataset

- Download ColonDB Dataset
- Do not add the dataset to git; it stays local under `datasets/`.
- Place the archive or extracted contents here (create the folder if it doesn't exist):

  ```text
  Surgical_Instrument/datasets/ColonDB/raw/
  ```

- Accepted archive types: `.zip`, `.tar`, `.tar.gz`, `.tgz`. Extract `.rar` downloads locally before copying.

### 2. Train and export the model

The user only needs to download and place the dataset. After that, the repo script can download the YOLO11n base model, train it, export it, and cache the final OpenVINO IR.

Model source:

- YOLO11n model family: https://docs.ultralytics.com/models/yolo11/
- Ultralytics model download/reference: https://docs.ultralytics.com/tasks/detect/
- Base weights direct URL: https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt (~5.4 MB, downloaded automatically by Ultralytics during `make backend-bootstrap`)

**Expected flow: train from this repo**

> **Host prerequisite for `make backend-bootstrap`:** the training venv uses
> `torch+xpu`, which loads the Intel Level Zero user-mode driver **from the
> host**. Install the Intel GPU compute runtime (Level Zero + IGC + GMM) once
> before running the commands below, otherwise `make backend-bootstrap` will
> fail with `torch.xpu.is_available() == False` or a `zeInit` loader error.
> `make up` (containerised path) is unaffected — the Docker image installs
> them at build time.
>
> ```bash
> # One-time: add the Intel graphics apt repo (Ubuntu 24.04 "noble").
> sudo apt-get update && sudo apt-get install -y ca-certificates gnupg wget
> wget -qO - https://repositories.intel.com/gpu/intel-graphics.key \
>   | sudo gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg
> echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] \
> https://repositories.intel.com/gpu/ubuntu noble unified" \
>   | sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list
>
> # Level Zero + IGC + GMM runtime + OpenCL ICD.
> sudo apt-get update && sudo apt-get install -y \
>   libze1 libze-intel-gpu1 intel-igc-core-2 libigdgmm12 \
>   intel-opencl-icd intel-media-va-driver-non-free
>
> # Allow /dev/dri passthrough without sudo (log out/in after this).
> sudo usermod -aG render "$USER"
> ```
>
> Full rationale + verification snippet: [docs/user-guide/quickstart.md §1a](docs/user-guide/quickstart.md#1a-intel-gpu-compute-runtime-required-for-make-backend-bootstrap).

```bash
make backend-venv       # one-time Python environment with torch+xpu, Ultralytics, OpenVINO
make backend-bootstrap  # prepares ColonDB, trains YOLO11n, exports FP16 OpenVINO IR
```

`backend-bootstrap` does the full model preparation:

- reads the dataset from `datasets/ColonDB/raw/`
- extracts the archive if needed
- converts masks into YOLO bounding-box labels
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

- Train YOLO11n on ColonDB on another machine.
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
    --images-dir datasets/ColonDB/raw/ColonDB/images \
    --output videos/polyp_test.mp4 \
    --seconds 60 --fps 60 --width 1920 --height 1080
  ```

  This creates/overwrites `videos/polyp_test.mp4` using an H.264-compatible codec for the default app file-source pipeline. By default the script tries OpenCV first, then automatically falls back to system `ffmpeg` (`libx264`) when OpenCV H.264 is unavailable.

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

For subsequent runs:

```bash
make run
```

`make run` requires the cached IR and `.trained_ok` marker. If they are missing, it stops and
tells the user to prepare or seed the model first.

`make up` and `make run` both **auto-detect** any `/dev/video*` devices on
the host and layer in a compose override that makes them available to the
pipeline container. The UI's Settings modal is the primary runtime picker for
choosing between the recorded video and any attached camera — see
[docs/user-guide/runtime-configuration.md](docs/user-guide/runtime-configuration.md).

### 5. Pipeline cases (configurable via `make up`)

The DL Streamer pipeline is fully configurable at `make up` time via
environment variables (`SOURCE_KIND`, `DETECT`, `WATERMARK`, `MINIMAL`,
`SCHEDULING_POLICY`, `BATCH_SIZE`, `AUTOVIDEOSINK`). Three canonical shapes
cover the surface — file preview, minimal live camera, and tuned live
inference. Exact commands, generated `gst-launch-1.0` strings, verified
latency numbers, and troubleshooting can be found in the:
[Pipeline Cases document](docs/user-guide/pipeline-cases.md).



## Runtime configuration

See the [Runtime Configuration guide](docs/user-guide/runtime-configuration.md) to see how to
adjust the application Runtime UI controls, API endpoints, and the `make doctor`behavior.


## Repo layout (short)

```
Surgical_Instrument/
├── backend/
│   ├── main_server.py         # bootstrap FSM entrypoint
│   ├── pipeline/inference.py  # OpenVINO inference worker + rolling p99 stats
│   └── server/app.py          # Flask REST + SSE snapshot builder
├── ui/
│   └── src/
│       ├── components/ConfigPanel/      # source/device/session accordion (left)
│       ├── components/RightPanel/       # Pipeline Performance + Model & Input + Platform accordions
│       ├── redux/slices/detectionSlice.ts
│       ├── redux/middleware/sseMiddleware.ts
│       └── types/detection.ts
├── scripts/
│   └── create_endoscopy_video.py  # generate H.264 demo video from ColonDB frames
├── docker-compose.yaml
└── Makefile                   # up / run / down / logs / clean
```

## Disclaimer

Intel is committed to respecting human rights and avoiding complicity in human rights abuses. See [Intel's Global Human Rights Principles](https://www.intel.com/content/www/us/en/policy/policy-human-rights.html). Intel's products and software are intended only to be used in applications that do not cause or contribute to a violation of an internationally recognized human right.  
