Weld Porosity Detection
==============================

Prevent defects in real time with AI-powered monitoring.

Overview
########

AI and machine vision enable real-time detection of welding defects, ensuring immediate
corrective action before issues escalate. By leveraging the right camera and computing
hardware, a trained AI model continuously monitors the weld, halting the process
the moment a defect is detected. Deep learning AI processes video data at frame rates far
beyond human capability, delivering unmatched precision and reliability.

How It Works
############

This sample application consists of the following microservices:
DL Streamer Pipeline Server, Model Registry Microservice(MRaaS), MediaMTX server,
Coturn server, Open Telemetry Collector, Prometheus, Postgres and Minio.

You start the weld porosity classification pipeline with a REST request using
Client URL (cURL). The REST request will return a pipeline instance ID.
DL Streamer Pipeline Server then sends the images with overlaid bounding boxes through
webrtc protocol to webrtc browser client. This is done via the MediaMTX server used for
signalling. Coturn server is used to facilitate NAT traversal and ensure that the webrtc
stream is accessible on a non-native browser client and helps in cases where firewall is
enabled. DL Streamer Pipeline Server also sends the images to S3 compliant storage.
The Open Telemetry Data exported by DL Streamer Pipeline Server to Open Telemetry Collector
is scraped by Prometheus and can be seen on Prometheus UI. Any desired AI model from the
Model Registry Microservice (which can interact with Postgres, Minio and Geti Server for
getting the model) can be pulled into DL Streamer Pipeline Server and used for inference
in the sample application.

.. figure:: ./images/industrial-edge-insights-vision-architecture.drawio.svg
   :alt: Architecture and high-level representation of the flow of data through the architecture

   Figure 1: Architecture diagram

This sample application is built with the following Intel Edge AI Stack Microservices:

- `DL Streamer Pipeline Server <https://docs.openedgeplatform.intel.com/edge-ai-libraries/dlstreamer-pipeline-server/main/user-guide/Overview.html>`__
  is an interoperable containerized microservice based on Python for video ingestion and
  deep learning inferencing functions.
- `Model Registry Microservice <https://docs.openedgeplatform.intel.com/edge-ai-libraries/model-registry/main/user-guide/Overview.html>`__
  provides a centralized repository that facilitates the management of AI models

It also consists of the below Third-party microservices:

- `MediaMTX Server <https://hub.docker.com/r/bluenviron/mediamtx>`__
  is a real-time media server and media proxy that allows to publish webrtc stream.
- `Coturn Server <https://hub.docker.com/r/coturn/coturn>`__
  is a media traffic NAT traversal server and gateway.
- `Open telemetry Collector <https://hub.docker.com/r/otel/opentelemetry-collector-contrib>`__
  is a set of receivers, exporters, processors, connectors for Open Telemetry.
- `Prometheus <https://hub.docker.com/r/prom/prometheus>`__
  is a systems and service monitoring system used for viewing Open Telemetry.
- `Postgres <https://hub.docker.com/_/postgres>`__
  is object-relational database system that provides reliability and data integrity.
- `Minio <https://hub.docker.com/r/minio/minio>`__
  is high performance object storage that is API compatible with
  Amazon S3 cloud storage service.

Features
########

This sample application offers the following features:

- High-speed data exchange with low-latency compute.
- Real-time AI-assisted classification of defects during the welding process.
- On-premise data processing for data privacy and efficient use of bandwidth.
- Interconnected welding setups deliver analytics for quick and informed tracking and
  decision making.

.. toctree::
   :hidden:

   overview-architecture
   system-requirements
   get-started
   troubleshooting-guide
   how-to-change-input-video-source
   how-to-deploy-using-helm-charts
   how-to-enable-mlops
   how-to-manage-pipelines
   how-to-run-multiple-ai-pipelines
   how-to-scale-video-resolution
   how-to-use-an-ai-model-and-video-file-of-your-own
   how-to-run-store-frames-in-s3
   how-to-view-telemetry-data
   how-to-start-mqtt-publisher
   how-to-use-gpu-for-inference
   how-to-use-opcua-publisher
   api-reference
   environment-variables
   release_notes/Overview
