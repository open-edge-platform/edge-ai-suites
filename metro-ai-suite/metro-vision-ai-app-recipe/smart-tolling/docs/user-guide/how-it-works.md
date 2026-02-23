# How It Works

This section provides a high-level view of how the application integrates with a
typical system architecture.

![High-Level System Diagram](./_assets/smart_tolling_architecture.png)

## Inputs

Video recordings are used to simulate a live feed from cameras deployed at a toll.
The application can be configured to work with live cameras.

- **Video Files** - Tolling cameras that capture videos simultaneously from front,
  rear and side profiles.
- **Scene Database** - Pre-configured intersection scene with satellite view of
  tolling area, calibrated cameras and regions of interest.

## Core (Processing)

- [**Video Analytics**](./how-it-works/perception-layer.md) - Deep Learning Streamer Pipeline Server
  (DL Streamer Pipeline Server) utilizes a pre-trained object detection model
  to [generate object detection metadata](./how-it-works/#zero-copy-video-pipeline) and and a local
  NTP server for synchronized timestamps. This metadata is published to the MQTT broker.
- **Sensor Fusion** - Scene Controller Microservice fuses the metadata from
  video analytics utilizing scene data obtained through the Scene Management API.
  It uses the fused tracks and the configured analytics (regions of interest)
  to generate events that are published to the MQTT broker.
- [**Aggregate Scene Analytics**](./how-it-works/analytics-pipeline.md#node-red-transformation) - Region of interests
  analytics are read from the MQTT broker and
  [stored in an InfluxDB bucket](./how-it-works/analytics-pipeline.md#storage-influxdb) that enables time series
  analysis through Flux queries.

## Live Feed Output

- Fused object tracks are available on the MQTT broker and visualized through
  the Scene Management UI.
- [Aggregated toll analytics](./how-it-works/analytics-pipeline.md) are visualized
  through a Grafana dashboard.

## Workflow

1. Video loops or RTSP is fed into DL Streamer.
2. Trained AI models detect vehicles and license plates.
3. Metadata is published to MQTT.
4. SceneScape maps detections to scene regions to get exact location of objects on the scene.
5. Exit events are generated when vehicles leave the region.
6. Node-RED processes only finalized exit events by subscribing to SceneScape topics.
7. Data is written to InfluxDB for system to access for consistent information.
8. Grafana visualizes real time and historical data enabling access to metrics
   and vehicle details.

## Learn More

- [Perception Layer](./how-it-works/perception-layer.md)
- [Optimizations](./how-it-works/optimization.md)
- [Analytics Pipeline](./how-it-works/analytics-pipeline.md)
- [System Requirements](./get-started/system-requirements.md)
- [Get Started](./get-started.md)
- [API Reference](./api-reference.md)
- [Support and Troubleshooting](./troubleshooting.md)

<!--hide_directive
:::{toctree}
:hidden:

./how-it-works/perception-layer
./how-it-works/optimization
./how-it-works/analytics-pipeline

:::
hide_directive-->
