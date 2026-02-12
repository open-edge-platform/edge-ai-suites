# How It Works

This section provides a high-level view of how the application integrates with a
typical system architecture.

![High-Level System Diagram](./_assets/smart_tolling_architecture.png)

## Diagram Description

### Inputs

Video recordings are used to simulate a live feed from cameras deployed at a toll.
The application can be configured to work with live cameras.

- **Video Files** - Tolling cameras that capture videos simultaneously from front,
  rear and side profiles.
- **Scene Database** - Pre-configured intersection scene with satellite view of
  tolling area, calibrated cameras and regions of interest.

### Core (Processing)

- [**Video Analytics**](./perception-layer.md) - Deep Learning Streamer Pipeline Server
  (DL Streamer Pipeline Server) utilizes a pre-trained object detection model
  to [generate object detection metadata](#zero-copy-video-pipeline) and and a local
  NTP server for synchronized timestamps. This metadata is published to the MQTT broker.
- **Sensor Fusion** - Scene Controller Microservice fuses the metadata from
  video analytics utilizing scene data obtained through the Scene Management API.
  It uses the fused tracks and the configured analytics (regions of interest)
  to generate events that are published to the MQTT broker.
- [**Aggregate Scene Analytics**](#node-red-transformation) - Region of interests
  analytics are read from the MQTT broker and
  [stored in an InfluxDB bucket](#storage-influxdb) that enables time series
  analysis through Flux queries.

### Live Feed Output

- Fused object tracks are available on the MQTT broker and visualized through
  the Scene Management UI.
- [Aggregated toll analytics](#analytics-pipeline-downstream) are visualized
  through a Grafana dashboard.

### Workflow

1. Video loops or RTSP is fed into DL Streamer.
2. Trained AI models detect vehicles and license plates.
3. Metadata is published to MQTT.
4. SceneScape maps detections to scene regions to get exact location of objects on the scene.
5. Exit events are generated when vehicles leave the region.
6. Node-RED processes only finalized exit events by subscribing to SceneScape topics.
7. Data is written to InfluxDB for system to access for consistent information.
8. Grafana visualizes real time and historical data enabling access to metrics
   and vehicle details.

## Optimizations

The system achieves high-throughput processing on Edge hardware through specific
optimizations defined in `config.json`. The [`docker-compose.yml`](./_assets/docker-compose.yml)
file mentions all the services and the pipelines are configured in `config.json` file.

### Zero-Copy Video Pipeline

Unlike standard OpenCV pipelines that copy frames to CPU RAM, this solution utilizes **VASurface Sharing plugin**.

- **Mechanism:** Decoded video frames remain in GPU memory (`video/x-raw(memory:VAMemory)`).
- **Benefit:** Zero-copy inference eliminates PCIe bandwidth bottlenecks, reducing end-to-end latency by ~40%.
- **Config Evidence:** `pre-process-backend=va-surface-sharing` used in all `gvadetect` elements.

### Dynamic ROI Inference (Hierarchical Execution)

To maximize efficiency, heavy neural networks (like Axle Counting) do not run on the full 4K frame.

- **Logic:** The "Vehicle Type" model runs first to find the bounding box.
- **Optimization:** The Axle model is configured with `inference-region=roi-list`,
  forcing it to execute *only* within the coordinates of the detected vehicle.
- **Impact:** Reduces pixel processing load by >80% for sparse traffic scenes.

### Hybrid Workload Distribution

The pipeline intelligently maps models to available accelerators to prevent resource contention:

- **GPU (Flex Series):** Handles heavy convolution tasks (Vehicle Detection, LPR, Axle Counting).
- **CPU (Xeon):** Handles lighter classification tasks (Vehicle Color) and post-processing adapters (`gvapython`).

## Analytics Pipeline (Downstream)

Raw metadata is valuable, but actionable insights come from the Analytics Pipeline.

## Node-RED Transformation

- **Input:** The **MQTT IN Node** subscribes to `scenescape/event/region/+/+/objects`.
- **Logic:** The **Function node** aggregates counts per region and calculates **Dwell Time** (congestion).
- **Output:** The **InfluxDB OUT Node** writes normalized data points to InfluxDB.

![Node-RED Flow](./_assets/smart_tolling_nodered.png)

### Storage (InfluxDB)

InfluxDB acts as a single source of truth. All critical and shared data is
stored in one location, ensuring every user and system accesses the same,
accurate and consistent information.

![InfluxDB Dashboard 1](./_assets/smart_tolling_influx_db.png)

### Visualization (Grafana)

The system ships with a pre-configured dashboard (`anthem-intersection.json` schema)
focusing on Traffic Volume, Flow Efficiency and Safety Alerts.

![Grafana Dashboard 1](./_assets/garfana_Dashboard1.png)

## Learn More

- [System Requirements](./get-started/system-requirements.md)
- [Get Started](./get-started.md)
- [API Reference](./api-reference.md)
- [Support and Troubleshooting](./troubleshooting.md)

<!--hide_directive
:::{toctree}
:hidden:

./perception-layer

:::
hide_directive-->
