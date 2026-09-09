# Get Started - Deploy Surgical Instrument

This is a deployment guide for the Docker Compose stack:

- `hls-si-endoscopy` — single Python service that captures frames from a Basler
  camera, USB/V4L2 webcam, or video file; runs OpenVINO inference; and renders
  results with an OpenGL vsync presenter.

> **Model required first.** The stack expects an OpenVINO IR at
> `models/yolo11n_polyp/best_openvino_model/best.xml`. If you do not already
> have one, follow [Model Preparation](./get-started/model-preparation.md)
> before continuing.

## Prerequisites

Before you start, refer to [System Requirements](./get-started/system-requirements.md)
to confirm your setup compatibility.

### Host tools

The app runs entirely in a container, so the host only needs a small set of tools:

| Tool | Required? | Why |
|---|---|---|
| **Docker Engine + Compose plugin** | Yes | The app runs via `make up` → `docker compose up`. |
| **make** | Yes | `make up` is the entry point. |
| **git** | To get the code | Needed for `git clone` (skip if you use a release archive). |
| **python3** | No | Python runs inside the container; the host does not need it. |

The easiest way to satisfy these on Ubuntu is the bundled setup script, which
installs/verifies Docker + Compose + `make` + `git`, adds your user to the
`docker` group, installs the Intel client GPU stack (Level Zero + OpenCL +
iHD VA-API), and configures a proxy only if you provide one:

```bash
# No proxy (typical):
make setup-prerequisites

# Behind a corporate proxy, export it first:
HTTP_PROXY=http://your-proxy:port HTTPS_PROXY=http://your-proxy:port \
  make setup-prerequisites
```

Log out and back in afterward (or run `newgrp docker`) so docker-group
membership takes effect. On non-Ubuntu hosts, install Docker manually per the
[Docker docs](https://docs.docker.com/engine/install/).

### Models and videos

The application does not ship with the trained model binaries or demo videos.
You need to place these resources under the host paths that are bind-mounted
into the container:

```text
models/yolo11n_polyp/best_openvino_model/best.xml
models/yolo11n_polyp/best_openvino_model/best.bin
videos/polyp_test.mp4
```

The Makefile mounts `../models` to `/models` and `../videos` to `/videos` by
default. Override with `MODELS_DIR` and `VIDEOS_DIR` when the host layout is
different.

A quick sanity check for all runtime prerequisites (Docker, `/dev/dri`, cached
IR, demo video, Intel L0 stack):

```bash
make doctor
```

---

## 1. Discover the camera and CPU topology

```bash
make list-cameras   # prints Basler serial(s) + model -> use as SERIAL=
make show-cores     # prints P-core / E-core CPU sets  -> use with CPU_CAPTURE/CPU_INFERENCE/CPU_DISPLAY
```

## 2. Bring the stack up

`make up` supports two image sources, controlled by the `REGISTRY` flag.

### 2a. Pull the image from the registry (default)

`REGISTRY=true` is the default. `make up` pulls the prebuilt image at `TAG`
(default `latest`) from `REGISTRY_URL` and starts it with the current runtime
knobs applied through Docker Compose.

```bash
# Low-latency live Basler camera (recommended tuned defaults).
# vsync-phase-locked capture + fixed 2ms exposure + core-pinned, SCHED_FIFO
# capture/inference/display threads — the configuration validated for lowest
# camera-to-screen latency.
make up SOURCE=camera LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 EXPOSURE_US=2000 \
  DEVICE=GPU FRAME_SKIP=3 SERIAL=<SERIAL_NUMBER> \
  CPU_CAPTURE=1 CPU_INFERENCE=2 CPU_DISPLAY=3 RT_PRIORITY=80

# Minimal low-latency (let the app pick exposure / no core pinning).
make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER>

# Baseline free-running camera.
make up SOURCE=camera SERIAL=<SERIAL_NUMBER>

# Video file (loops on EOF).
make up SOURCE=file SOURCE_ARG=/videos/polyp_test.mp4

# USB / V4L2 webcam.
make up SOURCE=webcam DEVICE_INDEX=0

# Select the OpenVINO inference device (default: GPU).
make up SERIAL=<SERIAL_NUMBER> DEVICE=CPU
make up SERIAL=<SERIAL_NUMBER> DEVICE=NPU   # requires /dev/accel on the host
```

### 2b. Build the image from source

`REGISTRY=false` builds the image locally from `docker/Dockerfile` before
starting the stack.

```bash
make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER> REGISTRY=false
```

## 3. Watch logs

```bash
make logs
```

Per-stage latency CSV is streamed to stdout when `LATENCY_TRACE=1` (implied by
`LOWLATENCY=1`):

```text
clock_time, trigger_to_grab_ms, grab_to_display_ms, trigger_to_display_ms, infer_ms, disp_fps, cap_fps
```

## 4. Stop the stack

```bash
make down                 # stop + remove the container
make clean                # also remove the built image
```

Press **ESC** inside the display window to quit the app.

---

## Command reference

| Command | What it does |
|---|---|
| `make up` | Pull or build the image and start the stack with current runtime knobs. |
| `make down` | Stop and remove the container. |
| `make logs` | Follow container logs. |
| `make clean` | Stop the stack and remove the built image. |
| `make list-cameras` | List connected Basler cameras (serial + model). |
| `make show-cores` | Show P-core / E-core CPU sets for `--cpu-*` pinning. |
| `make help` | List all targets. |

For every runtime knob, CLI flag, and low-latency variant, see
[Runtime Configuration](./runtime-configuration.md).



<!--hide_directive
:::{toctree}
:hidden:

System Requirements <./get-started/system-requirements.md>
Model Preparation <./get-started/model-preparation.md>

:::
hide_directive-->
