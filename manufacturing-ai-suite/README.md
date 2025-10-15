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

|              |             |            |
|:-------------|:------------|:-----------|
| [HMI Augmented worker](./hmi-augmented-worker/)                                           | A RAG-enabled HMI application deployable on type-2 hypervisors.                                 | [Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/hmi-augmented-worker/index.html)                     |
| [Pallet Defect Detection](./industrial-edge-insights-vision/apps/pallet-defect-detection) | Real-time pallet condition monitoring via multiple AI models.                                   | [Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/pallet-defect-detection/index.html)                  |
| [PCB Anomaly Detection](./industrial-edge-insights-vision/apps/pcb-anomaly-detection)     | Real-time anomaly detection in printed circuit boards (PCB) with AI vision systems.             | [Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/pcb-anomaly-detection/index.html)                    |
| [Weld Porosity](./industrial-edge-insights-vision/apps/weld-porosity)                     | Real-time detection of welding defects.                                                         | [Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/weld-porosity/index.html)                            |
| [Worker Safety Gear Detection](./industrial-edge-insights-vision/apps/worker-safety-gear-detection) | Real-time visual analysis of safety gear compliance for workers.                      | [Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/worker-safety-gear-detection/index.html)             |
| [Wind Turbine Anomaly Detection](./industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection)                       | A time series use case of detecting anomalous power generation patterns relative to wind speed. | [Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/wind-turbine-anomaly-detection/index.html)           |


**Main tools and AI Libraries the Suite uses**

|              |             |
|:-------------|:------------|
| [Deep Learning Streamer](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/libraries/dl-streamer)                                     | A framework for building optimized media analytics pipelines powered by OpenVINO&trade; toolkit.                                 |
| [Deep Learning Streamer Pipeline Server](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server)  | A containerized microservice, built on top of GStreamer, for development and deployment of video analytics pipelines.            |
| [Model Registry](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-registry)                                      | Providing capabilities to manage the lifecycle of an AI model.                                                                   |
| [Time Series Analytics Microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/time-series-analytics)           | Built on top of **Kapacitor**, a containerized microservice for development and deployment of time series analytics capabilities |
| [Intel&reg; Geti&trade; SDK](https://github.com/open-edge-platform/geti-sdk)                                                                          | A python package containing tools to interact with a Geti&trade; server via the REST API, helping you build a full MLOps for vision based use cases. |
| [OpenVINO&trade; toolkit](https://github.com/openvinotoolkit/openvino)                                                                                | An open source toolkit for deploying performant AI solutions across Intel hardware for generative and conventional AI models.    |
| [OpenVINO&trade; Model Server](https://github.com/openvinotoolkit/model_server)                                                                       | An OpenVINO server solution for enabling remote model inference for AI applications deployed on low-performance devices.         |
