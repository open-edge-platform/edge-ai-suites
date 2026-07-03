# Surgical Instrument — Quickstart

Deployment guide for the two-service Docker stack: `surgical-backend` (Flask 3 + Ultralytics + OpenVINO) and `surgical-ui` (nginx + React SPA).

The UI is **health-gated on the backend**: the browser tab will not answer until `surgical-backend` reports `/api/readiness → ready`. On first boot this window is 20–35 minutes while YOLO11n trains on CVC-ColonDB on the Intel Arc iGPU. Subsequent boots take seconds because the trained IR is cached in `./models/`.

---

## 1. Host prerequisites

| Requirement | Notes |
|---|---|
| Linux with Docker Engine ≥ 24 and `docker compose` v2 | Rootless Docker works if `/dev/dri` is accessible. |
| Intel Arc iGPU (Meteor Lake / Lunar Lake / Arrow Lake) or discrete Arc GPU | Container inherits the host driver via `/dev/dri` passthrough. |
| Host groups `render` and `video` exist | The Makefile auto-detects the GIDs. |
| ≈ 15 GB free disk | 6 GB image, 2 GB dataset + cache, remainder for training checkpoints. |

Verify iGPU visibility on the host before starting:

```bash
ls -l /dev/dri/renderD*
getent group render
getent group video
```

---

## 2. One-time: drop the CVC-ColonDB dataset

The bootstrap will refuse to train without the dataset. We do not redistribute it; you must download it directly from the CVC lab (research use only).

1. Visit **https://pages.cvc.uab.es/CVC-Colon/index.php/databases/** and download the CVC-ColonDB archive after accepting their terms. Citation: *Bernal, Sánchez, Vilariño (2012) Pattern Recognition 45(9), 3166–3182*.
2. Place the archive or extracted folder here:

   ```
   Surgical_Instrument/datasets/CVC-ColonDB/raw/
   ```

   Accepted archive types: `.zip`, `.tar`, `.tar.gz`, `.tgz`. If your download is `.rar`, extract it locally first.
3. That's it — the bootstrap will auto-detect images + masks on first launch, convert binary masks to YOLO bounding-box labels, split 70/15/15, and write `data.yaml`.

If you already have a trained IR (e.g. from the POC), skip training entirely by seeding it into `models/`:

```bash
make assets   # copies best.xml + best.bin from poc/st2_app if present
```

The presence of `models/yolo11n_polyp/best_openvino_model/best.xml` **and** `models/yolo11n_polyp/.trained_ok` short-circuits the bootstrap to `ready` in seconds.

---

## 3. Bring the stack up

```bash
make up
```

This runs `docker compose up -d --build` with `RENDER_GID` and `VIDEO_GID` auto-detected from the host. Compose builds the backend image (torch+xpu wheels + OpenVINO + Ultralytics) and the UI image (Vite build → nginx).

The `surgical-ui` service declares `depends_on: surgical-backend: condition: service_healthy`, so it will not start listening on `:8080` until the backend passes its `/api/readiness` HEALTHCHECK. The backend healthcheck uses a **45-minute `start_period`** to absorb first-boot training.

### Follow first-boot progress

```bash
make logs
```

Expect to see the FSM walk through:

```
[boot] state=initializing
[boot] state=checking_cache
[boot] state=downloading_dataset      (skipped if raw/ already populated)
[boot] state=preparing_dataset
[boot] state=downloading_weights      (~5 MB yolo11n.pt)
[boot] state=training                 (~15-25 min, ~50 epochs)
[boot] state=exporting                (Ultralytics → OpenVINO IR)
[boot] state=ready
[server] READY
```

### Open the UI

Once the backend is healthy the UI starts and answers on `http://localhost:8080` (override with `make up UI_HOST_PORT=9090`). `make up` and `make run` also print the LAN URL (e.g. `http://10.223.23.206:8080`) so you can open it from another machine on the same network.

Click **Start** in the top toolbar to kick off inference. The video panel begins streaming annotated frames and the KPI blocks on the right start populating within ~1 second.

---

## 4. What the UI shows

Everything on-screen is driven by the backend's `/api/events` SSE stream (~1 Hz snapshot) plus the `/api/video_feed` MJPEG. There is no client-side state polling.

**Left column**

| Block | Source | Notes |
|---|---|---|
| Video feed | `/api/video_feed` (MJPEG) | 1080p H.264 source, model-annotated |
| **Detection Status** (hero card, under the video) | `analytics.polyp_detection` | Live pill (`DETECTED` / `NOT DETECTED`) + confidence, plus a `SESSION` sub-bar with **cumulative polyp detections**, **% of frames with a detection**, and **positive-frame count** — reset on `POST /api/reset`. |

**Right column — Pipeline Performance accordion**

| Column | Source | Meaning |
|---|---|---|
| Workload | static | `Polyp Detection` |
| Model | static | `yolo11n` |
| Device | `pipeline_performance.workloads[0].device` | Colored pill: `GPU` / `CPU` / `NPU` |
| FPS | `pipeline_performance.workloads[0].fps` | Rolling mean over the last ~5 s |
| **Infer** | `pipeline_performance.workloads[0].infer_ms` | Mean OpenVINO inference latency (excludes pre/post) |
| **P99** | `pipeline_performance.workloads[0].latency_p99_ms` | True p99 of end-to-end frame latency (rolling deque of 120, `numpy.percentile`) |
| Status | lifecycle FSM | `running` / `paused` / `stopped` |

Below the table:

- **End-to-end summary bar** — pipeline FPS · decode resolution · uptime · total frames processed.
- **Model & Input block** — model name, precision (`FP16 OpenVINO IR`), task/dataset (`Polyp Detection` on `CVC-ColonDB`), **video source** resolution (e.g. `1080p H.264 (looped)`), **model input** tensor size (`640x640`), and the runtime **device**.

**Right column — Platform accordion**

Live CPU / GPU / NPU utilization from `intel-npu-info` and `nvidia-smi`-style samplers, refreshed on every SSE snapshot.

---

## 5. Common overrides

| Variable | Default | Meaning |
|---|---|---|
| `UI_HOST_PORT` | `8080` | Only host-published port. |
| `DETECTION_DEVICE` | `xpu` | Set to `cpu` on a host without an Arc iGPU. |
| `RENDER_GID` / `VIDEO_GID` | auto | Override if the host has non-standard render/video group IDs. |

Example: run the whole stack CPU-only on port 9000:

```bash
make up UI_HOST_PORT=9000 DETECTION_DEVICE=cpu
```

---

## 6. Troubleshooting

| Symptom | Diagnosis / Fix |
|---|---|
| `docker compose up` fails with `permission denied` on `/dev/dri/renderD128` | The `render` group GID inside the container doesn't match the host. Confirm `getent group render` on the host and re-run `make up` (the Makefile auto-detects). |
| `surgical-backend` never becomes healthy; logs show `preparing_dataset → error` | The CVC-ColonDB archive isn't at `datasets/CVC-ColonDB/raw/`. See step 2. |
| Browser at `http://localhost:8080` returns "connection refused" | The UI is still waiting for the backend HEALTHCHECK. `docker ps` will show `surgical-ui` as `Created` (not `Up`). Follow `make logs surgical-backend` until you see `state=ready`. |
| Training runs on CPU instead of iGPU (very slow) | The container did not see `/dev/dri`. Check `docker exec surgical-backend ls /dev/dri` and `python -c "import torch; print(torch.xpu.is_available())"`. |
| `torch.xpu` prints `False` inside the container | Level-Zero library missing. The backend image ships `libze1`; if your host has a mismatched driver, install `intel-i915-dkms` (or the equivalent for your kernel) and reboot. |

---

## 7. Stop / clean up

```bash
make down                 # stop + remove containers, keep volumes + IR
make clean                # also drop the surgical-cache named volume + built images
```

The trained IR under `./models/` is a bind-mount and survives `make clean`. Delete it manually to force a full re-train on next boot:

```bash
rm -rf models/yolo11n_polyp
```
