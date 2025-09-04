# Worker Safety Gear Detection

Automated quality control with AI-driven vision systems.

## Overview

This Sample Application enables real-time safety gear monitoring of workers by running inference workflows across multiple AI models. It connects multiple video streams from construction site cameras to AI-powered pipelines, all operating efficiently on a single industrial PC. This solution improves construction site safety and compliance by detecting safety gear related risks before they can impact operations.

## How It Works

This sample application consists of the following microservices: DL Streamer Pipeline Server, Model Registry Microservice(MRaaS), MediaMTX server, Coturn server, Open Telemetry Collector, Prometheus, Postgres and Minio.

You start the worker safety gear detection pipeline with a REST request using Client URL (cURL). The REST request will return a pipeline instance ID. DL Streamer Pipeline Server then sends the images with overlaid bounding boxes through webrtc protocol to webrtc browser client. This is done via the MediaMTX server used for signaling. Coturn server is used to facilitate NAT traversal and ensure that the webrtc stream is accessible on a non-native browser client and helps in cases where firewall is enabled. DL Streamer Pipeline Server also sends the images to S3 compliant storage. The Open Telemetry Data exported by DL Streamer Pipeline Server to Open Telemetry Collector is scraped by Prometheus and can be seen on Prometheus UI. Any desired AI model from the Model Registry Microservice (which can interact with Postgres, Minio and Geti Server for getting the model) can be pulled into DL Streamer Pipeline Server and used for inference in the sample application.

![Architecture and high-level representation of the flow of data through the architecture](./images/defect-detection-arch-diagram.png)

Figure 1: Architecture diagram

This sample application is built with the following Intel Edge AI Stack Microservices:

-   <a href="https://docs.openedgeplatform.intel.com/edge-ai-libraries/dlstreamer-pipeline-server/main/user-guide/Overview.html">**DL Streamer Pipeline Server**</a> is an interoperable containerized microservice based on Python for video ingestion and deep learning inferencing functions.
-   <a href="https://docs.openedgeplatform.intel.com/edge-ai-libraries/model-registry/main/user-guide/Overview.html">**Model Registry Microservice**</a> provides a centralized repository that facilitates the management of AI models

It also consists of the below Third-party microservices:

- [MediaMTX Server](https://hub.docker.com/r/bluenviron/mediamtx) is a real-time media server and media proxy that allows to publish webrtc stream.
- [Coturn Server](https://hub.docker.com/r/coturn/coturn) is a media traffic NAT traversal server and gateway.
- [Open telemetry Collector](https://hub.docker.com/r/otel/opentelemetry-collector-contrib) is a set of receivers, exporters, processors, connectors for Open Telemetry.
- [Prometheus](https://hub.docker.com/r/prom/prometheus) is a systems and service monitoring system used for viewing Open Telemetry.
- [Postgres](https://hub.docker.com/_/postgres) is object-relational database system that provides reliability and data integrity.
- [Minio](https://hub.docker.com/r/minio/minio) is high performance object storage that is API compatible with Amazon S3 cloud storage service.


## Features

This sample application offers the following features:

- High-speed data exchange with low-latency compute.
- AI-assisted worker safety gear detection monitoring in real-time as workers enter the construction site.
- On-premise data processing for data privacy and efficient use of bandwidth.
- Interconnected construction site cameras deliver analytics for quick and informed tracking and decision making.