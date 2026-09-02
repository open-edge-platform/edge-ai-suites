# Surgical Instrument Sample App

> This application is for reference and evaluation purposes. It is not intended
> for direct use in clinical or diagnostic environments and is not validated for
> such a purpose.

Real-time polyp detection in endoscopic video using Intel hardware acceleration
(CPU / Intel iGPU / Intel NPU) with OpenVINO. The application is packaged as a
Docker Compose workload and supports Basler camera input, USB/V4L2 webcam input,
or video file input.

|   |   |
|---|---|
| **Model** | YOLO11n OpenVINO IR for polyp detection |
| **Inference** | Pure OpenVINO runtime |
| **Runtime** | Python application in Docker Compose |
| **Inputs** | Basler camera, USB/V4L2 webcam, or video file |
| **Display** | OpenGL vsync presenter with cv2/headless fallback |
| **Low latency** | Optional software-triggered or vsync-triggered Basler capture |

## Topology

The app runs as a single Docker Compose service with host networking for display,
GPU, and camera access.

```text
HOST display / GPU / USB
        |
        v
docker compose service: hls-si-endoscopy
        |
        +-- src/app.py       capture / inference / display pipeline
        +-- /models          OpenVINO IR bind mount
        +-- /videos          demo video bind mount
```

## Model Preparation

The Docker Compose stack expects an OpenVINO IR at
`models/yolo11n_polyp/best_openvino_model/best.xml` and (for `SOURCE=file`) a
demo video at `videos/polyp_test.mp4`. Two ways to get there:

- **Pull a prebuilt image from the registry** — the default `make up` flow.
  Skip the training steps below.
- **Build the model locally** — install host prerequisites, download the
  REAL-Colon dataset subset, train YOLO11n on the Intel iGPU, and export a
  FP16 OpenVINO IR:

```bash
./setup.sh                      # install Docker + Intel L0 stack (Ubuntu 24.04)
make check-l0                   # verify host GPU stack
make backend-venv               # create .venv-backend (torch+xpu, Ultralytics, OpenVINO)
./download_realcolon_subset.sh  # 7-study REAL-Colon subset (~74 GB) from figshare 22202866
make backend-bootstrap          # dataset -> train -> FP16 OpenVINO IR (cache-first)
make doctor                     # preflight all runtime prerequisites
```

See [Model Preparation](docs/get-started/model-preparation.md) for the full
end-to-end walkthrough, dataset options, and cache-reset instructions.

## Quickstart

From this directory, start the default low-latency Basler camera flow:

```bash
make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER>
```

By default, `make up` pulls the prebuilt image from the registry.

To build the image from local source instead:

```bash
make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER> REGISTRY=false
```

Follow logs or stop the stack:

```bash
make logs
make down
```

## Common Commands

List connected Basler cameras and use the printed serial with `SERIAL=`:

```bash
make list-cameras
```

Show CPU topology for optional capture, inference, and display thread pinning:

```bash
make show-cores
```

Run against a video file instead of a camera:

```bash
make up SOURCE=file SOURCE_ARG=/videos/polyp_test.mp4
```

Run against a USB/V4L2 webcam:

```bash
make up SOURCE=webcam DEVICE_INDEX=0
```

## Model and Video Inputs

The container expects model and video assets to be mounted from the host:

```text
models/yolo11n_polyp/best_openvino_model/best.xml
models/yolo11n_polyp/best_openvino_model/best.bin
videos/polyp_test.mp4
```

The default Makefile mounts `../models` to `/models` and `../videos` to
`/videos`. Override those paths when needed:

```bash
make up MODELS_DIR=/path/to/models VIDEOS_DIR=/path/to/videos SERIAL=<SERIAL_NUMBER>
```

## Documentation

- [Overview](docs/index.md)
- [Model preparation (optional local training)](docs/get-started/model-preparation.md)
- [Get started](docs/get-started.md)
- [System requirements](docs/get-started/system-requirements.md)
- [Runtime configuration](docs/runtime-configuration.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Release notes](docs/release-notes.md)

## Repo Layout

```text
surgical-instrument/
├── Makefile
├── setup.sh                       # host prerequisite installer (Docker + Intel L0)
├── download_realcolon_subset.sh   # REAL-Colon 7-study subset downloader (~74 GB)
├── backend/                       # optional local training + OpenVINO export
│   ├── bootstrap/                 # dataset auto-detect, train, export
│   ├── config/model.yaml          # training + dataset config (env-var expanded)
│   ├── main_bootstrap.py
│   └── requirements.txt
├── datasets/
│   └── REAL-Colon/helper/         # vendor full-corpus downloader (60 studies)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yaml
├── docs/
│   ├── index.md
│   ├── get-started.md
│   ├── get-started/
│   │   ├── system-requirements.md
│   │   └── model-preparation.md
│   ├── runtime-configuration.md
│   ├── troubleshooting.md
│   └── release-notes.md
├── scripts/
│   └── create_endoscopy_video.py
└── src/
    ├── app.py
    ├── config.py
    ├── detector.py
    ├── display.py
    ├── sources.py
    ├── utility.py
    └── requirements.txt
```
