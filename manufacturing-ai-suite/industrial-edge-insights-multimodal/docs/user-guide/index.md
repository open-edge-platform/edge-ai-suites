# Industrial Edge Insights - Multimodal

Multimodal Weld Defect Detection sample application demonstrates how to use AI
at the edge to identify defects in manufacturing environments by analyzing both
image and time series sensor data.

By combining results from image-based defect detection and time series anomaly
detection using logical "AND" or "OR" operations, the system provides:

- more robust and accurate identification of potential defects,
- enhances reliability, reduces false positives, and supports smarter
  decision-making for maintenance,
- helps manufacturers enhance product quality, reduce inspection time, and
  minimize costly rework by enabling proactive defect detection on the
  factory floor.

Industrial quality relies on safety and reliability, and manual inspections
are time-consuming and prone to human error. Therefore, we have developed the
application to leverage deep learning models to automate defect detection,
improving both accuracy and efficiency.

**Key features include:**

- Multi-modal data fusion: Combines visual inspection (images) and sensor data
  (such as current, voltage, and temperature) for comprehensive defect detection.
- Real-time inference: Processes data at the edge for immediate feedback and
  reduced latency.
- Configurable alerts: Notifies operators of detected defects to enable
  timely intervention.
- Extensible pipeline: Supports integration with additional data sources
  and models.

[The application](./weld-defect-detection/index.md) utilizes camera-based
visual inspection and sensor data analysis to identify anomalies in welding data.

## Software Stack

This section documents the minimum software stack that **Multimodal Weld Defect Detection**
uses from the broader Open Edge Platform (Edge AI Libraries, tools, and microservices), so
you can see exactly what is required to run this sample application versus what the platform
additionally offers. This application fuses a vision stack and a time-series stack, and can
optionally be extended with a Generative AI / agentic layer.

### Core Stack

The following components are deployed by default through `docker-compose.yml`:

| Category | Component | Role in this sample application |
|---|---|---|
| AI runtime | OpenVINO™ Toolkit | Inference runtime used internally by DL Streamer to run the weld defect classification model |
| AI microservice | DL Streamer Pipeline Server | Runs the vision (camera-based) weld inspection pipeline |
| Data ingestion | Telegraf | Collects/forwards simulated weld sensor data (current, voltage, temperature) |
| Data storage | InfluxDB | Time-series database used by the TICK stack |
| AI microservice | Time Series Analytics Microservice (built on Kapacitor) | Runs the sensor-data anomaly-detection UDF |
| Custom microservice | Fusion Analytics | Combines vision and time-series detection results with configurable `AND`/`OR` logic |
| Visualization | Grafana | Dashboards for fused weld quality results |
| Microservice | Eclipse Mosquitto (MQTT broker) | Transports detection/fusion results |
| Microservice | MediaMTX, Coturn | Re-streams processed video over RTSP/WebRTC |
| Microservice | SeaweedFS (S3-compatible storage) | Stores processed images/weld inspection frames |
| Microservice | nginx | Reverse proxy for the application endpoints |

### Optional Add-ons

| Component | Role | Enabled via |
|---|---|---|
| vLLM (OpenVINO-optimized) + Insights Workbench | Generates an AI text explanation of a detected weld defect from vision/sensor context | `docker-compose-vllm.yml` — [Deploy vLLM Service](./how-to-guides/how-to-deploy-vllm-service.md) |
| Agentic workflow: `apm-agent` (LangGraph meta-agent: Policy, Analysis, Ticketing agents) | Reasons over fusion results and produces root-cause analysis and structured maintenance tickets — this is the "Ops/Maintenance Co-pilot" behavior | `docker-compose-agentic.yml` — [Deploy the Agentic Workflow](./how-to-guides/how-to-deploy-agent-workflow.md) |
| OpenVINO™ Model Server (OVMS) | Serves the LLM consumed by the agentic workflow (`apm-llm`) | `docker-compose-agentic.yml` |
| Model Download microservice | Downloads the model(s) used by the agentic workflow (`apm-model-download`) | `docker-compose-agentic.yml` |
| Metrics Collector, Prometheus | Collects agentic workflow metrics (`apm-metrics`, `apm-prometheus`) | `docker-compose-agentic.yml` |
| Agentic UI (`multimodal-agentic-ui`) | Web UI for triggering and reviewing agentic weld quality analysis runs | `docker-compose-agentic.yml` |
| Intel® Geti™ Software | Used offline to train and export the weld defect classification model as OpenVINO™ IR | [How to Fine-Tune a VLM](./how-to-guides/how-to-fine-tune-vlm.md), model README under `configs/dlstreamer-pipeline-server/models/` |
| PyTorch (training only) | Used offline for VLM fine-tuning (LoRA adapters for defect explainability) — not part of the deployed containers | [training/vlm-fine-tuning](../../training/vlm-fine-tuning/README.md) |
| Helm / Kubernetes | Alternative deployment path for the core (non-agentic, non-vLLM) stack | [Deploy with Helm](./get-started/deploy-with-helm.md) |

### Minimum Configuration

See [System Requirements](./get-started/system-requirements.md) for the minimum hardware and
software configuration for this sample application.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
how-to-guides.md
weld-defect-detection/index.md
troubleshooting.md
Release Notes <release-notes.md>

:::
hide_directive-->
