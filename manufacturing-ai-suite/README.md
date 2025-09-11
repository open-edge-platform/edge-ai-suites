
**Manufacturing AI Suite (MAS)** is a comprehensive toolkit for building, deploying, and scaling AI applications in industrial environments. Powered by Intel’s Edge AI technologies, it enables real-time integration and innovation with optimized hardware.

It includes:
•	Tools for AI acceleration (for example, MQTT/OPC UA support, analytics libraries, camera system software)
•	A complete AI pipeline for closed-loop systems
•	Benchmarking support for evaluating performance across time series, vision, and generative AI workloads

The Manufacturing AI Suite helps you develop solutions for:
•	**Production Workflow**: Detect defects, optimize efficiency
•	**Workplace Safety**: AI-driven risk reduction
•	**Real-Time Insights**: Local data processing, trend tracking
•	**Automation**: Instant alerts and corrective actions

**Sample Applications**

| Applications | Description | User Guide |
|:------------|:------------|:-----------|
| [HMI Augmented worker](./hmi-augmented-worker/) | Demonstrates an RAG-enabled HMI application a Hypervisor environment, allowing a standard HMI deployment setup. | https://docs.openedgeplatform.intel.com/edge-ai-suites/hmi-augmented-worker/main/user-guide/overview.html |
| [Pallet Defect Detection](industrial-edge-insights-vision/apps/pallet-defect-detection) | Provides automated quality control with AI-driven vision systems. | [Link](https://docs.openedgeplatform.intel.com/edge-ai-suites/pallet-defect-detection/main/user-guide/Overview |
| [PCB Anomaly Detection](industrial-edge-insights-vision/apps/pcb-anomaly-detection) | Provides real-time anomaly detection in printed circuit boards (PCB) by running with AI-driven vision systemspenedgeplatform.intel.com/edge-ai-suites/pcb-anomaly-detection/main/user-guide/Overview.html) |
| [Weld Porosity](industrial-edge-insights-vision/apps/weld-porosity) | Prevents defectsng AI-powered monitoring. AI and machine vision enable real-time detection of welding defects, ensuring immediate recovery before issues escalate. | https://docs.openedgeplatform.intel.com/edge-ai-suites/weld-porosity/main/user-guide/Overview.html |
| [Worker Safety Gear Detection](industrial-edge-insights-vision/apps/worker-safety-gear-detection) | Provides real-time monitoring of worker safety gear with AI-driven visionopenedgeplatform.intel.com/edgetes/worker-safety-gear-detection/main/user-guide/Overview.html |
| [Wind Turbine Anomaly Detection](wind-turbine-anomaly-detection/) | Demonstrates a time series use case by detecting the anomalous power generation patterns relative to wind speed. | [Link](https://docs.openedgeplatform.intel.com/2025.1/edge-ai-suites/wind-turbine-anomaly-detection.html |


Some of the the  important components and AI Libraries the Suite uses for its industrial
and manufacturing use cases are:

- [Deep Learning Streamer](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/libraries/dl-streamer): A pipeline framework that provides that enables building optimized media analytics pipeline powered by OpenVINO&trade; toolkit.
- [Deep Learning Streamer Pipeline Server](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server): Built on top of GStreamer, a containerized microservice for development and deployment of video analytics pipeline.
- [Model Registry](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-registry): Providing capabilities to manage lifecycle of an AI model.
- [Time Series Analytics Microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/time-series-analytics): Built on top of **Kapacitor**, a containerized microservice for development and deployment of time series analytics capabilities
- [Intel&reg; Geti&trade; SDK](https://github.com/open-edge-platform/geti-sdk): A python package containing tools to interact with a Geti&trade; server via the REST API, helping you build a full MLOps for vision based use cases.
- [OpenVINO&trade; toolkit](https://github.com/openvinotoolkit/openvino): An open source toolkit for deploying performant AI solutions across Intel hardware for generative and conventional AI models.
- [OpenVINO&trade; Model Server](https://github.com/openvinotoolkit/model_server): An OpenVINO server solution for enabling remote model inference for AI applications deployed on low-performance devices.
