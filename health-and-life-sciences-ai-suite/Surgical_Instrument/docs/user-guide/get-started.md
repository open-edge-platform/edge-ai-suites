# Get Started

This guide walks you through cloning the repository, preparing the dataset and model, and running the Surgical Instrument application.

## Prerequisites

Ensure your system meets the following requirements before proceeding.

### Hardware

- Intel Core Ultra (Meteor Lake) or 12th Gen Intel Core or newer (x86_64, AVX2 required).
- Intel Arc iGPU (Meteor Lake / Lunar Lake / Arrow Lake) or discrete Intel Arc GPU.
- Minimum 16 GB RAM (32 GB recommended).
- Minimum 20 GB free disk space (40 GB+ recommended to accommodate Docker images, dataset, training checkpoints, and cached IR).

### Software

- Ubuntu 24.04 LTS (recommended and validated); Ubuntu 22.04 LTS is also supported.
- Docker Engine 24.x or newer with Docker Compose v2 (`docker compose`).
- `make` and `git`.
- Host groups `render` and `video` must exist. Verify with:

  ```bash
  getent group render
  getent group video
  ls -l /dev/dri/renderD*
  ```

> **Note:** This application is for **reference and evaluation purposes only**. It is **not intended for clinical or diagnostic use** and is not validated as a medical device.

---

## 1. Clone the Repository

Use sparse checkout to download only the Surgical Instrument component.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch main \
  https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set health-and-life-sciences-ai-suite/Surgical_Instrument
cd health-and-life-sciences-ai-suite/Surgical_Instrument
```

---

## 2. Corporate Proxy Setup (if applicable)

If you are behind a corporate proxy, configure it before running any `make` targets — both the Docker image build and the runtime YOLO11n weight download need proxy access.

**Option A (recommended, persistent):** copy `.env.example` to `.env` and set the proxy values:

```bash
cp .env.example .env
# Edit .env and set HTTP_PROXY, HTTPS_PROXY, NO_PROXY
```

**Option B (ad-hoc):** export proxy variables in your shell before running `make`:

```bash
export HTTP_PROXY=http://proxy.your-corp.com:912
export HTTPS_PROXY=http://proxy.your-corp.com:912
export NO_PROXY=localhost,127.0.0.1,surgical-pipeline,surgical-backend,surgical-ui
```

`docker-compose.yaml` forwards these values to both `docker build` and the running containers automatically.

---

## 3. Prepare the Dataset

The application trains a YOLO11n polyp detection model on **CVC-ColonDB** at first boot. The dataset is not included in the repository; you must download it directly.

1. Visit **https://pages.cvc.uab.es/CVC-Colon/index.php/databases/** and download the CVC-ColonDB archive after accepting their terms.

   Alternatively, use the Kaggle mirror (requires a personal Kaggle API token):

   ```bash
   kaggle datasets download longvil/cvc-colondb
   ```

2. Place the archive or extracted folder here (create the directory if it does not exist):

   ```
   Surgical_Instrument/datasets/CVC-ColonDB/raw/
   ```

   Accepted archive types: `.zip`, `.tar`, `.tar.gz`, `.tgz`. If your download is `.rar`, extract it locally first.

3. That is all — the application bootstrap will auto-detect the images and masks on first launch, convert them to YOLO bounding-box labels, split 70/15/15, and write `data.yaml`.

> **Third-Party Content**
>
> *In the course of using these Intel-provided instructions, users may choose to download content (e.g., datasets) created and distributed by third parties. In doing so, these users acknowledge and agree that they have reviewed background information about the content and agreed to the governing license.*
>
> ***Notice**: Intel does not create the content and does not warrant its accuracy or quality. By accessing the third-party content, you are indicating your acceptance of the terms associated with that content and warranting that your use complies with the applicable license.*

### Optional: Seed a Pre-trained Model (skip training)

If you already have a trained OpenVINO IR (e.g., from a previous run or a POC machine), copy it into `models/` to skip the 20–35 minute first-boot training:

```bash
make assets
```

The presence of `models/yolo11n_polyp/best_openvino_model/best.xml` and `models/yolo11n_polyp/.trained_ok` short-circuits the bootstrap to `ready` in seconds on subsequent boots.

---

## 4. Run the Application

Start all services:

```bash
make up
```

This builds the images and starts three containers:

| Service              | Port (host) | Purpose                                                |
| -------------------- | ----------- | ------------------------------------------------------ |
| `surgical-backend`   | internal    | Flask 3 control plane — bootstrap, REST API, SSE stream |
| `surgical-pipeline`  | internal    | GStreamer + DL Streamer — inference, latency tracer    |
| `surgical-ui`        | 8080        | nginx reverse-proxy serving the React SPA              |

> **First boot:** The backend orchestrates the full train pipeline (dataset prep → YOLO11n training → OpenVINO IR export) on the Intel Arc iGPU. This takes **20–35 minutes**. `surgical-ui` will not answer on `:8080` until the backend reports `/api/readiness → ready`. Follow progress with:
>
> ```bash
> make logs
> ```

To use a different host port:

```bash
make up UI_HOST_PORT=9090
```

To run all workloads on CPU (hosts without an Intel Arc iGPU):

```bash
make up DETECTION_DEVICE=CPU
```

---

## 5. Open the Dashboard

Once the backend is ready, open a browser and navigate to:

```
http://localhost:8080
```

Or use the LAN URL printed by `make up` to open it from another machine on the same network (e.g., `http://10.223.23.206:8080`).

In the UI:

1. In the **Config** panel on the left, select a source (`file` or `basler`) and a source argument (video file path or Basler camera serial number).
2. Select the inference **Device** (`GPU`, `CPU`, or `NPU`).
3. Click **Start** to begin inference.

The right column populates within ~1 second with:

- **Pipeline Performance table** — FPS, mean/P50/P90/P95/P99 latency.
- **Model & Input block** — model name, precision (`FP16 OpenVINO IR`), dataset, source resolution, tensor size, device.
- **Platform accordion** — CPU / GPU / NPU utilization.

---

## 6. Stop the Application

```bash
make down
```

This stops and removes all containers. The trained IR in `models/` is preserved so the next `make up` skips training entirely.

---

## 7. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `permission denied` on `/dev/dri/renderD128` | The `render` group GID inside the container doesn't match the host. Run `getent group render` on the host and re-run `make up` — the Makefile auto-detects the GID. |
| `surgical-backend` never becomes healthy; logs show `preparing_dataset → error` | The CVC-ColonDB archive is missing from `datasets/CVC-ColonDB/raw/`. See [step 3](#3-prepare-the-dataset). |
| Browser at `http://localhost:8080` returns "connection refused" | The UI is waiting for the backend HEALTHCHECK. Run `docker ps` — `surgical-ui` will show `Created` (not `Up`). Follow `make logs` until you see `state=ready`. |
| `make up` fails with a curl timeout during image build | You are behind a corporate proxy but have not configured it. See [step 2](#2-corporate-proxy-setup-if-applicable). |
| Training completes but inference shows no detections | The model input tensor is `640×640`. Verify the source video is a valid H.264 file and that `DETECTION_DEVICE` matches available hardware. |
