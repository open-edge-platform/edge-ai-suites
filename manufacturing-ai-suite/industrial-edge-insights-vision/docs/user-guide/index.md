# Industrial Edge Insights - Vision

Vision applications enable AI-powered real time monitoring for quality control purposes.
Their use cases cover detecting deviations and anomalies in manufacturing processes
by running inference workflows across multiple AI models on video feeds from
visual monitoring systems located on-site, all operating efficiently on a single
industrial PC.

[Pallet Defect Detection](./pallet-defect-detection/index.md) and [PCB Anomaly Detection](./pcb-anomaly-detection/index.md) seamlessly combine multiple microservices to provide real-time video analysis
enhancing quality control and compliance of manufacturing processes. Using AI-driven
real-time analytics, edge devices can detect manufacturing defects and anomalies
that could impact quality, efficiency and safety of manufacturing operations. See
[Get Started](./get-started.md) for installation instructions.

## Blueprint

This section documents the minimum software stack that **Pallet Defect Detection** and **PCB
Anomaly Detection** use from the broader Open Edge Platform (Edge AI Libraries, tools, and
microservices), so you can see exactly what is required to run these sample applications
versus what the platform additionally offers.

### Core Stack

The following components are deployed by default through `docker-compose.yml` (or the
equivalent Helm chart in `helm/`):

| Category | Component | Role in this sample application |
|---|---|---|
| AI runtime | OpenVINO™ Toolkit | Inference runtime used internally by DL Streamer to run the detection/classification model |
| AI microservice | DL Streamer Pipeline Server | Core microservice: runs the GStreamer/DL Streamer video analytics pipeline (`gvadetect`/`gvaclassify`) |
| Microservice | MediaMTX | Re-streams processed video over RTSP/WebRTC |
| Microservice | Coturn | TURN/STUN relay used for WebRTC video playback |
| Microservice | Eclipse Mosquitto (MQTT broker) | Transports detection results/metadata |
| Microservice | MinIO | S3-compatible storage for saved frames |
| Microservice | Prometheus, OpenTelemetry Collector | Metrics and telemetry collection |
| Microservice | nginx | Reverse proxy for the application endpoints |

### Optional Add-ons

These components are not part of the default deployment but are documented and supported for
specific workflows:

| Component | Role | Enabled via |
|---|---|---|
| Model Download microservice | Downloads OpenVINO™ and Intel® Geti™-trained models to demonstrate an MLOps update flow | [Enable MLOps](./how-to-extend-functionality/enable-mlops.md) |
| Intel® Geti™ Software | Used offline to train and export the Pallet Defect Detection (YOLOX) and PCB Anomaly Detection (Anomalib-based) models as OpenVINO™ IR | [Generate a Model with Geti™](./pallet-defect-detection/how-to-guides/generate-model-with-geti.md) |
| Helm / Kubernetes | Alternative deployment path for the same microservices on a Kubernetes cluster | [Deploy with Helm](./get-started/deploy-with-helm.md) |

> **Note:** Model training and export (Geti™, PyTorch, Anomalib) happen outside the deployed
> application containers — only the resulting OpenVINO™ IR model is consumed at runtime by
> DL Streamer.

### Stack Component System Requirements

Each shared component brings its own hardware/software requirements, documented at the
source rather than repeated here:

| Component | System Requirements |
|---|---|
| DL Streamer Pipeline Server | [System Requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/get-started/system-requirements.html) |
| DL Streamer | [System Requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/system_requirements.html) |
| Model Download microservice | [System Requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started/system-requirements.html) |
| Intel® Geti™ Software | [Installation Guide](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/installation-guide) |

### Not Used by This Sample Application

The following platform capabilities are available on Open Edge Platform but are **not** part
of this sample application's stack: Generative AI / LLM models, RAG or chat microservices,
time-series analytics (TICK stack), and ROS-based robotics middleware.

[Win Vision AI](./win-vision-ai/index.md), in contrast to the other vision applications, is a more
generalised Python-based Windows application for running multiple AI inference pipelines on
any DL Streamer-compatible models, with flexible input and output options. It can be used as
a reference application and architectural template for building custom AI vision solutions on
Windows using Intel hardware.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
How To Customize <./how-to-customize/index.md>
How To Evaluate and Accelerate <./how-to-evaluate-accelerate/index.md>
How To Extend Functionality <./how-to-extend-functionality/index.md>
Sample Application: Pallet Defect Detection <./pallet-defect-detection/index.md>
Sample Application: PCB Anomaly Detection <./pcb-anomaly-detection/index.md>
api-reference.md
Troubleshooting <./troubleshooting.md>
Release Notes <release-notes.md>
./win-vision-ai/index.md

:::
hide_directive-->
