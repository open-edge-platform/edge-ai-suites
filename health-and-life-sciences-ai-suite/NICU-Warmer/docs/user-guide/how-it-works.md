# How It Works

This section describes the overall architecture of the NICU Warmer application and explains
the functions of each service.

## High-level Architecture

At a high level, the system is composed of several microservices that work together to ingest
video, run 5 AI models on Intel hardware (GPU, NPU, and CPU), aggregate results, and expose
them to a React dashboard for clinicians.

```
Video Source (file or uploaded .mp4)
    │
    ▼
decodebin3 (VA-API hardware decode)
    │
    ▼
gvadetect × 3 (GPU — Intel Arc / Meteor Lake)
    ├── person-detect-fp32    → Person bounding boxes
    ├── patient-detect-fp32   → Patient bounding boxes
    └── latch-detect-fp32     → Latch clip bounding boxes
    │
    ▼
gvapython: RppgCallback (CPU — OpenVINO)
    └── MTTS-CAN model → Heart Rate, Respiration Rate, Waveforms
    │
    ▼
gvapython: ActionCallback (NPU — OpenVINO)
    ├── Encoder: per-frame 512-dim feature extraction
    ├── Decoder: every 8 frames → Kinetics-400 classification
    ├── Motion analyser: frame-differencing → activity level
    └── NICU category mapping (11 categories)
    │
    ▼
gvapython: MQTTPublisher → MQTT topic "nicu/detections"
    │
    ▼
Flask Backend (MQTT subscriber)
    ├── RuntimeAggregator → normalise detections + rPPG + action
    ├── Per-workload device & status tracking
    ├── SSE stream → delta events to React UI
    │
    ▼
React Dashboard (http://localhost:3001)
    ├── VideoFeed (MJPEG from /video_feed)
    ├── Detection Cards (patient / caretaker / latch)
    ├── RppgCard (HR / RR waveform charts)
    ├── ActionCard (activity + motion level)
    ├── Pipeline Performance (per-model device + status)
    └── Resource Utilization (CPU / GPU / NPU / Memory / Power)
```

The main services in this deployment are:

- [DL Streamer Pipeline Server (DLSPS)](#dl-streamer-pipeline-server-service)
- [Backend](#backend-service)
- [MQTT Broker](#mqtt-broker-service)
- [Metrics Collector](#metrics-collector-service)
- [UI](#ui-service)

The following sections describe each service in more detail.

### DL Streamer Pipeline Server Service

The **nicu-dlsps** service is the core inference engine:

- Runs a GStreamer pipeline with VA-API hardware video decode, three `gvadetect` elements for
  object detection (GPU), and two `gvapython` callbacks for rPPG (CPU) and action recognition
  (NPU).
- All 5 AI models execute in a single pipeline at ~15 FPS, sharing decoded frames across
  workloads without redundant copies.
- Publishes all inference results (detections, rPPG vitals, action classifications) to MQTT
  topic `nicu/detections`.
- Exposes a REST API on port 8080 for pipeline lifecycle control (start, stop, status).
- Supports runtime device configuration — the backend can stop and restart the pipeline with
  different device assignments per workload.

### Backend Service

The **nicu-backend** service is the central aggregation and API layer:

- Subscribes to MQTT `nicu/detections` to receive raw inference results from DLSPS.
- Runs `RuntimeAggregator` to normalise detections, compute rPPG vital signs, and classify
  actions into NICU-specific categories.
- Tracks per-workload device assignments and pipeline status.
- Exposes Server-Sent Events (SSE) on `/events` with full snapshots (every 10s) and delta
  updates (every second) for the React dashboard.
- Provides MJPEG video streaming via `/video_feed` and latest frame via `/frame/latest`.
- Handles configuration endpoints for video upload, face ROI, and device selection.
- Manages pipeline lifecycle (prepare, start, stop) via the DLSPS REST API.

### MQTT Broker Service

The **nicu-mqtt** service provides message passing between pipeline and backend:

- Runs Eclipse Mosquitto on port 1883.
- Decouples the GStreamer pipeline (publisher) from the Flask backend (subscriber).
- Enables extensibility — additional consumers can subscribe to `nicu/detections` without
  modifying the pipeline.

### Metrics Collector Service

The **nicu-metrics-collector** service gathers hardware and system metrics from the host:

- Runs with `pid: host` and access to `/dev/dri` and system paths under `/sys` and `/proc`.
- Collects GPU, NPU, CPU, memory, and power statistics from Intel telemetry tools and kernel
  interfaces.
- Exposes metrics via REST API on port 9100, proxied by the backend to the dashboard.
- Provides platform information (processor model, GPU type, NPU availability, memory size,
  OS version).

### UI Service

The **nicu-ui** service provides the web-based monitoring dashboard:

- Built with React, TypeScript, Vite, and Redux Toolkit.
- Served via nginx reverse proxy on port 3001, which also proxies API calls to the backend.
- Connects to the backend SSE stream for real-time updates.
- Visualizes detections (patient, caretaker, latch), vital signs (HR/RR waveforms), action
  classification, pipeline performance, and hardware utilization.
- Provides a ConfigModal for runtime settings (video source, face ROI, device selection per
  workload) with "Apply & Restart" for live reconfiguration.

## Data and Control Flows

Putting the pieces together:

1. **Model download** — `make setup` runs a local Python script (`scripts/download_models.py`)
   to fetch all AI models and the test video to local directories.
2. **Pipeline startup** — the backend sends a start request to DLSPS with the configured
   pipeline template and device assignments.
3. **Video decode** — DLSPS decodes the video using VA-API hardware acceleration.
4. **Object detection** — three `gvadetect` elements run person, patient, and latch detection
   on GPU in parallel within the same pipeline.
5. **rPPG inference** — `gvapython` callback extracts face ROI, buffers frames, and runs
   MTTS-CAN on CPU to estimate heart rate and respiration.
6. **Action recognition** — `gvapython` callback runs encoder (per-frame) and decoder (every
   8 frames) on NPU, classifies activity, and computes motion level.
7. **MQTT publish** — all results are serialized and published to `nicu/detections`.
8. **Backend aggregation** — the backend subscribes to MQTT, normalizes results, and streams
   SSE events to connected UI clients.
9. **Dashboard rendering** — the React UI receives events and updates detection cards, vitals
   charts, performance tables, and resource utilization graphs in real time.
