# Live Video Search - Getting Started

## Overview

Live Video Search is a Metro AI Suite sample that adapts the VSS pipeline for semantic search on live Frigate streams. It ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and lets users select cameras, time ranges, and free‑text queries to retrieve ranked, playable clips with confidence scores while surfacing live system metrics. This guide starts the **Live Video Search** stack (Smart NVR + VSS Search) using Docker Compose.

## Prerequisites

- Verify that your system meets the [minimum requirements](./system-requirements.md).
- Install Docker tool: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).

## Project Structure

```text
live-video-search/
├── config/                        # Local configuration and assets
│   ├── frigate-config/            # Frigate camera configs (active + templates)
│   ├── mqtt-config/               # Mosquitto configuration
│   ├── telemetry/                 # Telemetry collector configs
│   └── nginx.conf                 # NGINX reverse proxy
├── data/                           # Runtime data (recordings, caches)
├── docker/                         # Compose files
│   ├── compose.search.yaml        # VSS Search stack
│   ├── compose.smart-nvr.yaml      # Smart NVR stack
│   └── compose.telemetry.yaml      # Telemetry collector
├── docs/                           # Documentation
│   └── user-guide/                # User guides
├── setup.sh                        # Main setup script
└── README.md                       # Project overview
```

## Set Required Environment Variables

Before running the application, you need to set several environment variables:

1. **Configure the registry**:
   The application uses registry URL and tag to pull the required images.

    ```bash
    export REGISTRY_URL=intel
    export TAG=1.3.4-rc1
    ```

2. **Set required credentials for some services**:
   Following variables **MUST** be set on your current shell before running the setup script:

    ```bash
    # MinIO credentials (object storage)
    export MINIO_ROOT_USER=<minio-user>
    export MINIO_ROOT_PASSWORD=<minio-pass>

    # PostgreSQL credentials (database)
    export POSTGRES_USER=<postgres-user>
    export POSTGRES_PASSWORD=<postgres-pass>

    # Embedding model for search
    export EMBEDDING_MODEL_NAME="CLIP/clip-vit-b-32"

    # MQTT credentials (Smart NVR)
    export MQTT_USER=<mqtt-user>
    export MQTT_PASSWORD=<mqtt-pass>
    ```

## Optional Environment Variables

You can customize the application behavior by setting the following optional environment variables before running the setup script:

1. **Control the frame extraction interval (Video Search Mode)**:

    The DataPrep microservice samples frames from uploaded videos according to the `FRAME_INTERVAL` environment variable. Set this variable before running `source setup.sh --search` to control how often frames are selected for processing.

    ```bash
    export FRAME_INTERVAL=15
    ```

    In the example above, DataPrep processes every fifteenth frame: each selected frame (optionally after object detection) is converted into embeddings and stored in the vector database. Lower values improve recall at the cost of higher compute and storage usage, while higher values reduce processing load but may skip important frames. If you do not set this variable, the service falls back to its configured default.

2. **Enable ROI consolidation (Video Search Mode)**:

    ROI consolidation groups overlapping object detections into merged regions of interest (ROIs) before cropping for embeddings. Enable this feature and tune it with the following environment variables:

    ```bash
    # Enable ROI consolidation (default: false)
    export ROI_CONSOLIDATION_ENABLED=true

    # IoU threshold for grouping ROIs (higher = stricter merging)
    export ROI_CONSOLIDATION_IOU_THRESHOLD=0.2

    # Only merge ROIs with the same class label when true
    export ROI_CONSOLIDATION_CLASS_AWARE=false

    # Expand merged ROIs by a fraction of width/height
    export ROI_CONSOLIDATION_CONTEXT_SCALE=0.2
    ```

    The IoU calculation follows the standard formula:

    $$
    IoU(A, B) = \frac{|A \cap B|}{|A \cup B|}
    $$

3. To use GPU acceleration for embedding generation, set the following variable before running the setup script:

    ```bash
    # Enable GPU embeddings
    export ENABLE_EMBEDDING_GPU=true
    ```

4. To explicitly select devices for DataPrep and the Multimodal Embedding service, set:

    ```bash
    # CPU or GPU
    export VDMS_DATAPREP_DEVICE=GPU
    export EMBEDDING_DEVICE=GPU
    ```

    If unset, both default to CPU. Setting `ENABLE_EMBEDDING_GPU=true` forces both to GPU.

## Configure Cameras

Edit `config/frigate-config/config.yml` to add or update camera inputs. This is the active Frigate configuration used at startup.

For reference, see the default template in `config/frigate-config/config-default.yml`.

## Start the Application

```bash
source setup.sh --start
```

## RTSP Test Stream (Out-of-Box)

Use the bundled sample video to spin up a looped RTSP stream and point Frigate at it.

1. Start the stack with the RTSP test services:

    ```bash
    source setup.sh --start-rtsp-test
    ```

2. Confirm the sample stream is live in Frigate:
    - Open `http://<host-ip>:5000` and select the `rtsp-garage` camera.

This uses `config/frigate-config/config-rtsp.yml` and publishes `config/videos/garage.mp4` over RTSP via `mediamtx`. Replace the RTSP URL in `config/frigate-config/config.yml` with your real camera streams when moving to production.

Access:

- VSS UI: `http://<host-ip>:12345`
- Smart NVR UI: `http://<host-ip>:7860`

## USB Camera (Direct Frigate Input)

Use a local USB camera (UVC/V4L2) as the Frigate input without creating an RTSP stream.

1. Plug in your USB camera and confirm the device node exists (typically `/dev/video0`).
2. Start the stack with the USB camera override:

    ```bash
    source setup.sh --start-usb-camera
    ```

3. Open Frigate UI at `http://<host-ip>:5000` and select the `usb-camera` feed.

Notes:

- If your camera is not `/dev/video0`, update `config/frigate-config/config-usb.yml` and/or set `USB_CAMERA_DEVICE` before starting:

    ```bash
    export USB_CAMERA_DEVICE=/dev/video2
    source setup.sh --start-usb-camera
    ```

- You can tune resolution and frame rate in `config/frigate-config/config-usb.yml` under `input_args`.

## How to Use Live Video Search

This workflow assumes the stack is running and cameras are configured in Frigate.

### Step 1: Add Clips to Search

1. Open Smart NVR UI at `http://<host-ip>:7860`.
2. Confirm camera streams are live.
3. Choose a camera and time range, then select **Add to Search**.

### Step 2: Run a Search Query

1. Open VSS UI at `http://<host-ip>:12345`.
2. Select one or more cameras.
3. Set a **time range** using either:
    - **UI time range picker**, or
    - **Natural‑language query** (examples below).
4. Enter a query and run search.

#### Example Queries (Time Range Parsing)

- `person seen in last 5 minutes`
- `car near garage in the past hour`
- `delivery truck last 30 minutes`

### Step 3: Review Results

Search results include clip timestamps, confidence scores, and metadata. Use the playback controls to jump to the exact event.

![Live Video Search - Review Results](_assets/Live-video-search-gif.gif)

### Tips

- If results are empty, confirm you added clips from Smart NVR UI.
- Narrow time ranges improve query latency and relevance.
- If telemetry is not visible, check that `vss-collector` is running.

## Stop or Reset

```bash
# Stop all containers
source setup.sh --down

# Remove volumes and live recordings
source setup.sh --clean-data
```

## Telemetry

Telemetry is enabled for Live Video Search and shows live system metrics in the VSS UI when the collector is connected.

## Troubleshooting

### No clips in search results

- Confirm you added clips via **Add to Search** in Smart NVR UI.
- Verify `VSS_SEARCH_URL` in `setup.sh` points to the internal endpoint.

### Search results empty after changing model

- If you changed `EMBEDDING_MODEL_NAME`, clean data and re‑ingest:
  - `source setup.sh --clean-data`
  - `source setup.sh --start`

### Telemetry information is not being displayed

- Verify `vss-collector` is running.
- Check Pipeline Manager status: `/manager/metrics/status`.

### MQTT connection errors

- Ensure `MQTT_USER` and `MQTT_PASSWORD` are set.
- Confirm `mqtt-broker` is healthy: `docker ps` and `docker logs mqtt-broker`.

### Stream disconnects

- Check Frigate logs for camera connection errors.
- Confirm RTSP sources are reachable and credentials are valid.

## References

- [Smart NVR docs](../../../../smart-nvr/docs/user-guide/get-started.md)
- [VSS API (public)](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/sample-applications/video-search-and-summarization/docs/user-guide)
