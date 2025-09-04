# Pallet Defect Detection

Pallet Defect Detection provides automated quality control with AI-driven vision systems. It enables real-time pallet condition monitoring by running inference workflows across multiple AI models. It connects multiple video streams from warehouse cameras to AI-powered pipelines, all operating efficiently on a single industrial PC. This solution enhances logistics efficiency and inventory management by detecting defects before they impact operations.
It is a cloud-native application composed of microservices, using pre-trained deep learning
models for video analysis. This sample application offers the following:

- High-speed data exchange with low-latency compute.
- AI-assisted defect detection in real-time as pallets are received at the warehouse.
- On-premise data processing for data privacy and efficient use of bandwidth.
- Interconnected warehouse delivery analytics for quick and informed decision making and tracking.

## Get Started

- [System Requirements](./docs/user-guide/system-requirements.md)
- [Setup guide](./docs/user-guide/get-started.md)
- [Overview](./docs/user-guide/overview.md)


## How It Works

You can read the overview of the architecture and logic of the application [here](./docs/user-guide/overview-architecture.md)

The components and services are as follows:

- **DL Streamer Pipeline Server** is a core component of the app. It receives video feed from
multiple cameras (four by default, simulated with a video recording). With pre-trained deep
learning models, it performs real-time object detection, classification, and tracking.
It recognizes vehicles in the parking lot and sends their 2D bounding boxes to Node-Red,
through the MQTT Broker. It also adds the detected bounding boxes on top of the video input,
consumed by the WebRTC Server.
- **Mosquitto MQTT Broker** is a message distribution service, passing data between these sends the raw coordinates of detected vehicles to Node-RED. The
feedback it receives is moved to Grafana to display.
- **WebRTC Server** serves video streams processed by the pipeline for
end-user visualization. It is supplemented by the Coturn signaling server and passes the feed
for display in Grafana.

It also consists of the following third-party microservices:

- [MediaMTX Server](https://hub.docker.com/r/bluenviron/mediamtx) is a real-time media server and media proxy that allows to publish webrtc stream.
- [Coturn Server](https://hub.docker.com/r/coturn/coturn) is a media traffic NAT traversal server and a gateway.
- [Open telemetry Collector](https://hub.docker.com/r/otel/opentelemetry-collector-contrib) is a set of receivers, exporters, processors, connectors for Open Telemetry.
- [Prometheus](https://hub.docker.com/r/prom/prometheus) is a systems and service monitoring system used for viewing Open Telemetry.
- [Postgres](https://hub.docker.com/_/postgres) is object-relational database system that provides reliability and data integrity.
- [Minio](https://hub.docker.com/r/minio/minio) is high performance object storage that is API compatible with Amazon S3 cloud storage service.

## Learn More

- [Helm based deployment](how-to-deploy-using-helm-charts.md)
- [MLOps using Model Registry](how-to-enable-mlops.md)
- [Run multiple AI pipelines](how-to-run-multiple-ai-pipelines.md)
- [Publish frames to S3 storage pipelines](how-to-run-store-frames-in-s3.md)
- [View telemetry data in Open Telemetry](how-to-view-telemetry-data.md)
- [Publish metadata to OPCUA](how-to-use-opcua-publisher.md)

## Troubleshooting

- [Troubleshooting Guide](troubleshooting-guide.md)
