# Get Started

Live Video Search is a Metro AI Suite sample that adapts the Visual Search and Summarization (VSS) pipeline for semantic search on live Frigate streams. It ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and lets users select cameras, time ranges, and free‑text queries to retrieve ranked, playable clips with confidence scores while surfacing live system metrics. This guide starts the **Live Video Search** stack (Smart NVR + VSS Search) using Docker Compose.

## Prerequisites

- Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- Install Docker tool: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).

## Project Structure

```text
live-video-search/
├── config/                        # Local configuration and assets
│   ├── frigate-config/            # Frigate camera configs (active + templates)
│   ├── mqtt-config/               # Mosquitto configuration
│   └── nginx.conf                 # NGINX reverse proxy
├── data/                           # Runtime data (recordings, caches)
├── docker/                         # Compose files
│   ├── compose.search.yaml        # VSS Search stack
│   ├── compose.search.milvus.yaml # Optional Milvus backend
│   ├── compose.smart-nvr.yaml      # Smart NVR stack
│   └── compose.metrics-manager.yaml # Metrics Manager integration
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
    export TAG=2026.2.0-rc1
    ```

    Use `TAG=2026.2.0-rc1` for this release workflow.

    **Override tags per stack (recommended for mixed release cycles):**

    Live Video Search combines two stacks that can be released on different cadences:
    - **VSS Search stack** (`compose.search.yaml`)
    - **Smart NVR stack** (`compose.smart-nvr.yaml`)

    Use stack-specific tag overrides when you need different image versions for each stack:

     ```bash
     export TAG=2026.2.0-rc1
     export VSS_STACK_TAG=2026.2.0-rc1
     export SMART_NVR_STACK_TAG=2026.2.0-rc1
     ```

    Why this is needed: a single shared `TAG` forces both stacks to use the same version, which does not match independent VSS and Smart NVR release cycles.

    Explicitly export `VSS_STACK_TAG` and `SMART_NVR_STACK_TAG` only when the two upstream stacks need different tags.

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
    export MULTIMODAL_EMBEDDING_MODEL="CLIP/clip-vit-b-32"

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

3. Select devices independently for indexing, object detection, and query embedding (each defaults to `CPU`):

    ```bash
    # CPU / GPU / NPU
    export DATAPREP_EMBEDDING_DEVICE=GPU   # indexing embedding in multimodal-dataprep
    export DATAPREP_DETECTION_DEVICE=GPU   # YOLOX detection in multimodal-dataprep
    export MME_EMBEDDING_DEVICE=GPU        # query embedding used by vector-retriever
    ```

    Set only the components that need accelerator offload. For example, set `DATAPREP_EMBEDDING_DEVICE=GPU` for GPU indexing while leaving `MME_EMBEDDING_DEVICE=CPU`, or configure them the other way around.

    > **NPU note:** Not all embedding backends and model combinations support NPU. Check supported model/device combinations at the [OpenVINO Supported Models](https://docs.openvino.ai/2026/documentation/compatibility-and-support/supported-models.html) page before selecting `NPU`.

4. **Select the vector database backend**:

    `video-search` always delegates similarity search to `vector-retriever`. The default VDMS mode uses the `vector-retriever-vdms` image. Milvus mode adds the standalone Milvus services and uses `vector-retriever-milvus`. Object storage remains on MinIO in both modes.

    ```bash
    # Default
    export VECTORDB_BACKEND=vdms

    # Optional Milvus backend
    export VECTORDB_BACKEND=milvus
    ```

    `VDB_METRIC_TYPE` and `VDB_INDEX_TYPE` configure the shared write/read contract between Multimodal DataPrep and Vector Retriever. Their defaults are `IP` and `FLAT`.

5. **Optional: tune continuous-ingestion watcher batches**:

    ```bash
    export VS_WATCH_BATCH_SIZE=10
    export VS_BATCH_JOB_POLL_INTERVAL_SECONDS=0.5
    export VS_BATCH_JOB_TIMEOUT_SECONDS=3600
    ```

    These settings control asynchronous DataPrep jobs for both the NVR Event
    Router continuous camera watcher and the Search MS directory watcher. They
    do not affect single event-rule clips or video summarization.

6. **Optional: disable live metrics**:

    Metrics Manager is enabled by default. Disable it before startup when host
    and DataPrep throughput metrics are not required:

    ```bash
    export ENABLE_METRICS_MANAGER=false
    ```

    This integration requires a coordinated `multimodal-dataprep` image that
    supports `MM_DATAPREP_METRICS_MANAGER_URL`. Publishing is non-blocking, so
    ingestion continues if Metrics Manager becomes unavailable. GPU and NPU
    panels remain empty when those devices are not present.

## Configure Cameras

Edit `config/frigate-config/config.yml` to add or update camera inputs. This is the active Frigate configuration used at startup.

For reference, see the default template in `config/frigate-config/config-default.yml`.

## Start the Application

```bash
source setup.sh --start
```

For Milvus, select the backend before starting any camera mode:

```bash
VECTORDB_BACKEND=milvus source setup.sh --start
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

1. Open VSS UI at `http://<host-ip>:12345`.
2. Click **Configure Cameras** and enable one or more cameras.
3. Confirm camera streams are live in Frigate (`http://<host-ip>:5000`).
4. Allow the watcher to ingest clips from enabled cameras.

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

![Live Video Search - Review Results](./_assets/Live-video-search.gif)

### Tips

- If results are empty, confirm cameras are enabled in **Configure Cameras** and clips have been ingested.
- Confirm `vector-retriever` is healthy and that its backend matches `VECTORDB_BACKEND`.
- Narrow time ranges improve query latency and relevance.
- If metrics are not visible, check that `metrics-manager` is healthy.

## Stop or Reset

```bash
# Stop all containers
source setup.sh --down

# Remove volumes, live recordings, and app networks
source setup.sh --clean-data
```

## Live Metrics

Metrics Manager is enabled by default. It collects host CPU, memory, and
accelerator metrics, while Multimodal DataPrep publishes embedding throughput
directly to it. The VSS UI consumes the combined stream through the same-origin
NGINX endpoint.

## Troubleshooting

### No clips in search results

- Confirm cameras are enabled in **Configure Cameras** in VSS UI.
- Verify `VSS_SEARCH_URL` in `setup.sh` points to the internal endpoint.

### Search results empty after changing model

- If you changed `MULTIMODAL_EMBEDDING_MODEL`, clean data and re‑ingest:
  - `source setup.sh --clean-data`
  - `source setup.sh --start`

### Metrics are not being displayed

- Verify `metrics-manager` is running and healthy:
  `docker compose -f docker/compose.search.yaml -f docker/compose.smart-nvr.yaml -f docker/compose.metrics-manager.yaml ps`.
- Check the same-origin health endpoint: `http://<host-ip>:12345/metrics-manager/health`.
- Inspect the live stream with
  `curl -N -H "Accept: text/event-stream" http://<host-ip>:12345/metrics-manager/metrics/stream`.
- Check Metrics Manager logs: `docker logs metrics-manager`.
- Confirm `ENABLE_METRICS_MANAGER` is not set to `false`.

### MQTT connection errors

- Ensure `MQTT_USER` and `MQTT_PASSWORD` are set.
- Confirm `mqtt-broker` is healthy: `docker ps` and `docker logs mqtt-broker`.

### Stream disconnects

- Check Frigate logs for camera connection errors.
- Confirm RTSP sources are reachable and credentials are valid.

### Docker network label mismatch on startup

If startup fails with an error like `network docker_live-video-network was found but has incorrect label`, clean up stale networks and restart:

- `source setup.sh --clean-data`
- `docker network rm docker_live-video-network live-video-network || true`
- `source setup.sh --start`

For RTSP test mode, start again with:

- `source setup.sh --start-rtsp-test`

### Accuracy of search results

The accuracy of search results vary based on multiple factors as listed in the [VSS troubleshooting guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/video-search-and-summarization/troubleshooting.html#accuracy-of-search-results). The same considerations hold true for Live Video Search, as the same VSS backend is used. If the user is using the RTSP test mode (`--start-rtsp-test`), the same video content is played in a loop and added to the embedding space. So, irrespective of the query, the same search results will be returned. It is advised not to use the RTSP test mode to check the accuracy of the search results; live camera feed is advised. Alternatively, accuracy aspects can be delegated to VSS since the backend is the same and Live Video Search is used exclusively to note the performance on a given hardware platform.

## References

- [Smart NVR docs](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/smart-nvr/get-started.html)
- [VSS API](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/video-search-and-summarization/api-reference.html)

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md
get-started/build-from-source.md
get-started/deploy-with-helm.md

:::
hide_directive-->
