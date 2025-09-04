# Weld Porosity Detection

Weld Porosity Detection prevents defects in real time using AI-powered monitoring. AI and machine vision enable real-time detection of welding defects, ensuring immediate corrective action before issues escalate. Using the right camera and computing hardware, a trained AI model continuously monitors the welds, halting the process the moment a defect is detected. Deep learning AI processes video data at frame rates far beyond human capability, delivering unmatched precision and reliability.

It is a cloud-native application composed of microservices, using pre-trained deep learning
models for video analysis. This sample application offers the following features:

- High-speed data exchange with low-latency compute.
- AI-assisted defect detection in real-time as pallets are received at the warehouse.
- On-premise data processing for data privacy and efficient use of bandwidth.
- Interconnected warehouses deliver analytics for quick and informed tracking and decision making.

## Get Started

To see the system requirements and other installation, see the following guides:

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

- [MediaMTX Server](https://hub.docker.com/r/bluenviron/mediamtx) is a real-time media server and media proxy that allows publishing webrtc stream.
- [Coturn Server](https://hub.docker.com/r/coturn/coturn) is a media traffic NAT traversal server and a gateway.
- [Open telemetry Collector](https://hub.docker.com/r/otel/opentelemetry-collector-contrib) is a set of receivers, exporters, processors, connectors for Open Telemetry.
- [Prometheus](https://hub.docker.com/r/prom/prometheus) is a systems and service monitoring system used for viewing Open Telemetry.
- [Postgres](https://hub.docker.com/_/postgres) is an object-relational database system that provides reliability and data integrity.
- [Minio](https://hub.docker.com/r/minio/minio) is a high performance object storage that is API compatible with Amazon S3 cloud storage service.
