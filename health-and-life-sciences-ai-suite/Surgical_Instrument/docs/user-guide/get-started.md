# Get Started - Deploy Surgical Instrument

This is a deployment guide for the three-service Docker stack:
- `surgical-backend` (Flask 3 + Ultralytics + OpenVINO bootstrap)
- `surgical-pipeline` (GStreamer + DL Streamer runtime)
- `surgical-ui` (nginx + React SPA)


## Prerequisites

Before you start, refer to [System Requirements](./get-started/system-requirements.md)
to confirm your setup compatibility.

If you work behind a proxy, see how to
[configure the app for a proxy](./get-started/system-requirements.md#corporate-proxy-setup).

The application does not ship with the medical dataset, trained model binaries, or demo videos.
You will need to collect these resources separately, as described in the following steps, and
store them locally. This keeps the demo reproducible without any dependency on a specific
machine.

---

## 1. Clone the repo and download the dataset

Open PowerShell and run:

```powershell
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-suites.git `
; cd edge-ai-suites `
; git sparse-checkout set health-and-life-sciences-ai-suite/Surgical_Instrument `
; cd health-and-life-sciences-ai-suite/Surgical_Instrument
```

Download the dataset and place it in the following local folder for datasets
(create it if it does not exist), for example:
`Surgical_Instrument/datasets/ColonDB/raw/`.


Archive support:
- `.zip`, `.tar`, `.tar.gz`, `.tgz` can be consumed directly.
- `.rar` must be extracted locally.

The bootstrap will now auto-detect images + masks on the first launch, convert binary
masks to YOLO bounding-box labels, split 70/15/15, and write `data.yaml`.




## 2. Train and export the model

Once the dataset is in the right place, the repo script will download the YOLO11n base model,
train it, export it, and cache the final OpenVINO IR.

Model references:
- YOLO11n model family: https://docs.ultralytics.com/models/yolo11/
- Ultralytics detect task: https://docs.ultralytics.com/tasks/detect/
- Base weights (~5.4 MB, downloaded automatically during `make backend-bootstrap`):
  https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt


If you already have a trained IR, you can seed it into `models/` and skip the training
entirely. The presence of both `models/yolo11n_polyp/best_openvino_model/best.xml` **and**
`models/yolo11n_polyp/.trained_ok` short-circuits the bootstrap to `ready` in seconds.

```bash
make assets   # copies best.xml + best.bin from poc/st2_app, if present
```


### 2.1 Optional: pre-place `yolo11n.pt` when GitHub is blocked

If downloading `yolo11n.pt` fails during bootstrap (for example, timeout / curl 28),
pre-download it on a machine with GitHub access and copy it into the backend cache:

```bash
# On a machine that can access GitHub:
curl -L -o yolo11n.pt \
        https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt

# On the target host (container must exist from at least one `make up`):
docker cp yolo11n.pt surgical-backend:/cache/weights/yolo11n.pt
docker restart surgical-backend
```

The backend checks `${CACHE_DIR}/weights/<model_name>.pt` (default
`/cache/weights/yolo11n.pt`) before fallback to auto-download.

### 2.2 Optional: pre-train and export model before `make up`

You can prepare the model artifacts ahead of time:

```bash
make backend-venv       # one-time Python environment: torch+xpu, Ultralytics, OpenVINO
make backend-bootstrap  # prepares ColonDB, trains YOLO11n, exports FP16 OpenVINO IR
```

`backend-bootstrap` does the full model preparation in sequence:

- reads the dataset from `datasets/ColonDB/raw/`
- extracts the archive if needed
- creates the train/validation/test split
- downloads the base `yolo11n.pt` weights through Ultralytics
- trains YOLO11n using the settings in `backend/config/model.yaml`
- exports the best checkpoint to FP16 OpenVINO IR
- writes the `.trained_ok` cache marker

Expected output layout:

```text
models/yolo11n_polyp/
├── .trained_ok
└── best_openvino_model/
        ├── best.xml
        ├── best.bin
        └── metadata.yaml
```

### 2.3 Optional: train elsewhere and import the IR

If you have trained YOLO11n on ColonDB on another machine:

1. Export the checkpoint to FP16 OpenVINO IR:

   ```bash
   yolo export model=/path/to/best.pt format=openvino half=True imgsz=640
   ```

2. Copy the result into this exact layout:

   ```text
   Surgical_Instrument/models/yolo11n_polyp/
   ├── .trained_ok
   └── best_openvino_model/
       ├── best.xml
       ├── best.bin
       └── metadata.yaml
   ```

   `best.xml` and `best.bin` are required. `metadata.yaml` is recommended because
   DL Streamer/OpenVINO can use the exported Ultralytics metadata.

3. Create the `.trained_ok` cache marker (checked by `make up` and the backend):

   ```bash
   mkdir -p models/yolo11n_polyp/best_openvino_model
   date -Is > models/yolo11n_polyp/.trained_ok
   ```





## 3. Generate demo video (required)

Fresh clones do not include `videos/polyp_test.mp4`. Generate it before
running `make doctor` / `make up`.

```bash
.venv-backend/bin/python scripts/create_endoscopy_video.py \
        --images-dir datasets/ColonDB/raw/ColonDB/images \
        --output videos/polyp_test.mp4 \
        --seconds 60 --fps 60 --width 1920 --height 1080
```

The script creates or overwrites `videos/polyp_test.mp4` using an H.264-compatible codec
(required by the default file-source pipeline). It tries OpenCV first, then falls back to
system `ffmpeg` (`libx264`) when needed.


## 4. Bring the stack up

Before bringing the stack up, run the preflight check:

```bash
make doctor   # checks Docker, accelerators, cached IR, demo video, and port 8080
```

Then discover the camera serial and the P-core set for your CPU:

```bash
make list-cameras   # prints Basler serial(s) -> SOURCE_ARG
make show-cores     # prints the P-core set    -> PIPELINE_GST_CORES
```

`make up` supports two image sources, controlled by the `REGISTRY` flag.

### 4a. Pull images from registry (default)

`REGISTRY=true` (the default) pulls the prebuilt images at `TAG` (default `latest`) and
starts them with `RENDER_GID` / `VIDEO_GID` auto-detected from the host — no local build
needed.

```bash
# Live Basler camera, tuned for fixed exposure + GPU detection with a live window.
make up SOURCE_KIND=basler SOURCE_ARG=<SERIAL_NUMBER> \
        BASLER_PIXEL_FORMAT=ycbcr422_8 BASLER_FIXED_CAMERA=1 BASLER_EXPOSURE_US=5000 \
        BASLER_THROUGHPUT_LIMIT=400000000 DETECT=1 DETECTION_DEVICE=GPU \
        AUTOVIDEOSINK=true PIPELINE_VIDEO_SINK=autovideosink

# Minimal live Basler camera (P-core pinned, free-running sink).
make up SOURCE_KIND=basler SOURCE_ARG=<SERIAL_NUMBER> \
        PIPELINE_GST_CORES=<P_CORES> PIPELINE_SINK_SYNC=false

# Default file source
make up              # trains YOLO11n on first boot if IR is not cached
make logs            # optional: follow readiness/startup logs
```

### 4b. Build images from source

`REGISTRY=false` builds every image locally from its Dockerfile (backend = torch+xpu wheels +
OpenVINO + Ultralytics, UI = Vite build → nginx, pipeline = DL Streamer + gencamsrc).

```bash
# Live Basler camera, tuned and built from source
make up SOURCE_KIND=basler SOURCE_ARG=<SERIAL_NUMBER> \
        BASLER_PIXEL_FORMAT=ycbcr422_8 BASLER_FIXED_CAMERA=1 BASLER_EXPOSURE_US=5000 \
        BASLER_THROUGHPUT_LIMIT=400000000 DETECT=1 DETECTION_DEVICE=GPU \
        AUTOVIDEOSINK=true PIPELINE_VIDEO_SINK=autovideosink REGISTRY=false

# Minimal live Basler camera, built from source
make up SOURCE_KIND=basler SOURCE_ARG=<SERIAL_NUMBER> \
        PIPELINE_GST_CORES=<P_CORES> PIPELINE_SINK_SYNC=false REGISTRY=false

# Default file source, built from source
make up REGISTRY=false     # trains YOLO11n on first boot if IR is not cached
make logs                  # optional: follow readiness/startup logs
```

The `surgical-ui` service declares `depends_on: surgical-backend: condition: service_healthy`,
so it will not start listening on `:8080` until the backend passes its `/api/readiness`
HEALTHCHECK. The backend healthcheck uses a **45-minute `start_period`** to absorb first-boot
training.

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

## 5. Open the UI

Note that the UI is **health-gated on the backend** -
the browser tab will not answer until `surgical-backend` reports `/api/readiness → ready`.
On the first boot this time window is 20–35 minutes while YOLO11n trains (an estimate for
ColonDB on the Intel® Arc™ iGPU).
Subsequent boots take seconds because the trained IR is cached in `./models/`.

Once the backend is healthy the UI starts and answers on `http://localhost:8080`
(you can override it with `make up UI_HOST_PORT=9090`).
`make up` and `make run` also print the LAN URL so you can access it from the same network.


Use the left **Config** accordion to pick source (`file` or `basler`), source argument,
and device, then click **Start** to kick off inference.
The right-side KPI blocks begin populating within ~1 second.

See more info in [User Interface](./user-interface.md).

For subsequent boots (IR already cached):

```bash
make run
```

`make run` requires cached IR files and `.trained_ok`. If they are missing,
prepare or seed the model artifacts first.

`make up` and `make run` auto-detect `/dev/video*` devices and layer in a
compose override so cameras are available to the pipeline container.

For runtime adjustments — source and device selection via the Settings modal,
video upload, and API endpoints for scripting — see
[Runtime Configuration](./runtime-configuration.md).


## 6. Stop / clean up

If you want to stop or restart the app, you have the following options:

```bash
make down                 # stop + remove containers, keep volumes + IR
```

```bash
make clean                # also drop the surgical-cache named volume + built images
```

The trained IR model under `./models/` is a bind-mount and survives `make clean`.
Delete it manually to force a full re-train on next boot:

```bash
rm -rf models/yolo11n_polyp
```




## Common overrides

| Variable                   | Default | Meaning                                                       |
|----------------------------|---------|---------------------------------------------------------------|
| `UI_HOST_PORT`             | `8080`  | Only host-published port.                                     |
| `DETECTION_DEVICE`         | `xpu`   | Set to `cpu` on a host without an Arc iGPU.                   |
| `RENDER_GID` / `VIDEO_GID` | auto    | Override if the host has non-standard render/video group IDs. |

Example: run the whole stack CPU-only on port 9000:

```bash
make up UI_HOST_PORT=9000 DETECTION_DEVICE=cpu
```

## Next: pipeline tuning

The DL Streamer pipeline can be tuned at launch time with environment
variables passed to `make up`, including:

- `SOURCE_KIND`
- `DETECT`
- `WATERMARK`
- `MINIMAL`
- `SCHEDULING_POLICY`
- `BATCH_SIZE`
- `AUTOVIDEOSINK`

Three common shapes are used in practice:

- File preview
- Minimal live camera
- Tuned live inference

### Basler camera tuning knobs

For live Basler sources (`SOURCE_KIND=basler`), the following variables tune the
camera and the display sink. See the tuned command in
[4a. Pull images from registry](#4a-pull-images-from-registry-default) for a full example.

| Variable                 | Default        | Meaning                                                                                     |
|--------------------------|----------------|---------------------------------------------------------------------------------------------|
| `BASLER_PIXEL_FORMAT`    | `ycbcr422_8`   | Camera pixel format (e.g. `ycbcr422_8`, `bayerbggr`).                                        |
| `BASLER_FIXED_CAMERA`    | `0`            | Set to `1` to disable auto-exposure/auto-gain and apply the fixed values below.             |
| `BASLER_EXPOSURE_US`     | unset          | Fixed exposure time in microseconds (applied only when `BASLER_FIXED_CAMERA=1`).            |
| `BASLER_THROUGHPUT_LIMIT`| `400000000`    | `DeviceLinkThroughputLimit` in bytes/sec; lifts the camera off its default cap.             |
| `DETECT`                 | `1`            | Set to `0` to run passthrough (no inference).                                                |
| `AUTOVIDEOSINK`          | unset          | `true` opens a live render window (`DISPLAY_VIEW=1` + `SINK_SYNC=true`); `false` disables it.|
| `PIPELINE_VIDEO_SINK`    | `autovideosink`| GStreamer sink element (e.g. `autovideosink`, `xvimagesink`).                                |





<!--hide_directive
:::{toctree}
:hidden:

System Requirements <./get-started/system-requirements.md>

:::
hide_directive-->
