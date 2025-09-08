
The Manufacturing AI Suite (MAS) is a comprehensive toolkit to build, deploy, and scale AI
applications in industrial environments. With Intel's advanced Edge AI technologies and
optimized hardware, it delivers a seamless development experience that supports real-time AI
integration and innovation.

The suite includes tools and software for AI acceleration—such as IoT protocol support (MQTT/OPC UA), accelerated libraries for data analytics, and system software for multi-interface cameras. It also offers an actionable AI pipeline for closed-loop systems and comprehensive benchmarking support for evaluating performance across time series, vision, and generative AI workloads.

The Manufacturing AI Suite helps you develop solutions for:
- Production Workflow: Efficiency optimizations, product quality (detect anomalies, defects, or variations)
- Workplace Safety: AI-based safety insights to help reduce risks
- Real-Time Insights: Improve the production process (local data processing, integration with existing manufacturing executions systems, tracking defect rates, identifying trends)
- Automation: Correct problems almost immediately (instant alerts, implementation of corrective actions)

The following sample applications will give you a quick preview of the suite's workflows
and show you how to utilize them in your use cases:

* [HMI Augmented worker](./hmi-augmented-worker/),
* [Pallet Defect Detection](industrial-edge-insights-vision/apps/pallet-defect-detection),
* [PCB Anomaly Detection](industrial-edge-insights-vision/apps/pcb-anomaly-detection),
* [Weld Porosity](industrial-edge-insights-vision/apps/weld-porosity),
* [Worker Safety Gear Detection](industrial-edge-insights-vision/apps/worker-safety-gear-detection),
* [Wind Turbine Anomaly Detection](wind-turbine-anomaly-detection/).


Some of the the more important components and AI Libraries the Suite uses for its industrial
and manufacturing use cases are:

- [Deep Learning Streamer](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/libraries/dl-streamer): A pipeline framework that provides that enables building optimized media analytics pipeline powered by OpenVINO&trade; toolkit.
- [Deep Learning Streamer Pipeline Server](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server): Built on top of GStreamer, a containerized microservice for development and deployment of video analytics pipeline.
- [Model Registry](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-registry): Providing capabilities to manage lifecycle of an AI model.
- [Time Series Analytics Microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/time-series-analytics): Built on top of **Kapacitor**, a containerized microservice for development and deployment of time series analytics capabilities
- [Intel&reg; Geti&trade; SDK](https://github.com/open-edge-platform/geti-sdk): A python package containing tools to interact with a Geti&trade; server via the REST API, helping you build a full MLOps for vision based use cases.
- [OpenVINO&trade; toolkit](https://github.com/openvinotoolkit/openvino): An open source toolkit for deploying performant AI solutions across Intel hardware for generative and conventional AI models.
- [OpenVINO&trade; Model Server](https://github.com/openvinotoolkit/model_server): An OpenVINO server solution for enabling remote model inference for AI applications deployed on low-performance devices.
