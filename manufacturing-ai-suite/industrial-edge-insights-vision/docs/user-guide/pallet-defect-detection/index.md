# Pallet Defect Detection

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-vision/apps/pallet-defect-detection">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-vision/apps/pallet-defect-detection/README.md">
     Readme
  </a>
</div>
hide_directive-->

Automated quality control with AI-driven vision systems.

## Overview

This Sample Application enables real-time pallet condition monitoring by running inference
workflows across multiple AI models. It connects multiple video streams from warehouse
cameras to AI-powered pipelines, all operating efficiently on a single industrial PC.
This solution enhances logistics efficiency and inventory management by detecting
defects before they impact operations.

## How It Works

This sample application consists of the following microservices:
DL Streamer Pipeline Server, MediaMTX server,Coturn server, 
Open Telemetry Collector, Prometheus and Minio.

You start the pallet defect detection pipeline with a REST request using Client URL (cURL).
The REST request will return a pipeline instance ID. DL Streamer Pipeline Server then sends
the images with overlaid bounding boxes through webrtc protocol to webrtc browser client.
This is done via the MediaMTX server used for signaling. Coturn server is used to
facilitate NAT traversal and ensure that the webrtc stream is accessible on a non-native
browser client and helps in cases where firewall is enabled. DL Streamer Pipeline Server
also sends the images to S3 compliant storage. The Open Telemetry Data exported by
DL Streamer Pipeline Server to Open Telemetry Collector is scraped by Prometheus and can
be seen on Prometheus UI. Any desired AI model from supported OpenVINO public models and 
Geti trained models can be downloaded with the help of Model Download Microservice
and can be made available to DL Streamer Pipeline Server for inference in the 
sample application.

![architecture and high-level representation of the flow of data through the architecture](./_assets/industrial-edge-insights-vision-architecture.drawio.svg)

This sample application is built with the following Intel Edge AI Stack Microservices:

- [DL Streamer Pipeline Server](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/index.html)
  is an interoperable containerized microservice based on Python for video ingestion
  and deep learning inferencing functions.
- [Model Download ](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-download)
  is a microservice to download AI models so that they may be used by DLStreamer Pipeline Server.

It also consists of the below Third-party microservices:

- [Nginx](https://hub.docker.com/_/nginx)
  is a high-performance web server and reverse proxy that provides TLS termination and unified HTTPS access.
- [MediaMTX Server](https://hub.docker.com/r/bluenviron/mediamtx)
  is a real-time media server and media proxy that allows to publish webrtc stream.
- [Coturn Server](https://hub.docker.com/r/coturn/coturn)
  is a media traffic NAT traversal server and gateway.
- [Open telemetry Collector](https://hub.docker.com/r/otel/opentelemetry-collector-contrib)
  is a set of receivers, exporters, processors, connectors for Open Telemetry.
- [Prometheus](https://hub.docker.com/r/prom/prometheus)
  is a systems and service monitoring system used for viewing Open Telemetry.
- [Minio](https://hub.docker.com/r/minio/minio)
  is high performance object storage that is API compatible with
  Amazon S3 cloud storage service.

## Features

This sample application offers the following features:

- High-speed data exchange with low-latency compute.
- AI-assisted defect detection in real-time as pallets are received at the warehouse.
- On-premise data processing for data privacy and efficient use of bandwidth.
- Interconnected warehouses deliver analytics for quick and informed tracking and
  decision making.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-to-guides
api-reference
troubleshooting
release-notes

:::
hide_directive-->
