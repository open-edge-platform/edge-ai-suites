
The Manufacturing AI Suite (MAS) empowers developers with a comprehensive toolkit to build, deploy, and scale AI applications in industrial environments. By leveraging Intel's advanced Edge AI technologies and optimized hardware, this AI Suite delivers a seamless development experience that supports real-time AI integration and innovation.

The suite includes tools and software for AI acceleration—such as IoT protocol support (MQTT/OPC UA), accelerated libraries for data analytics, and system software for multi-interface cameras. It also offers an actionable AI pipeline for closed-loop systems and comprehensive benchmarking support for evaluating performance across time series, vision, and generative AI workloads.

The Manufacturing AI Suite helps you develop solutions for:
- Production Workflow: Efficiency optimizations, product quality (detect anomalies, defects, or variations)
- Workplace Safety: AI-based safety insights to help reduce risks
- Real-Time Insights: Improve the production process (local data processing, integration with existing manufacturing executions systems, tracking defect rates, identifying trends)
- Automation: Correct problems almost immediately (instant alerts, implementation of corrective actions)

The important components from Edge AI Libraries that help you develop such pipelines for industrial and manufacturing AI use cases are:
- [Deep Learning Streamer Pipeline Server](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server): Built on top of GStreamer, a containerized microservice for development and deployment of video analytics pipeline.
- [Model Registry](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-registry): Providing capabilities to manage lifecycle of an AI model.
- [Object Store Microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/object-store/minio-store): MinIO based object store microservice to build generative AI pipelines.
- [Time Series Analytics Microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/time-series-analytics): Built on top of **Kapacitor**, a containerized microservice for development and deployment of time series analytics capabilities
- [Intel&reg; Geti&trade; SDK](https://github.com/open-edge-platform/geti-sdk): A python package containing tools to interact with an Intel&reg; Geti&trade; server via the REST API, helping you build a full MLOps for vision based use cases.

See sample applications such as [HMI Augmented worker](./hmi-augmented-worker/), [Pallet Defect Detection](industrial-edge-insights-vision/apps/pallet-defect-detection), [Weld Porosity](industrial-edge-insights-vision/apps/weld-porosity) and [Wind Turbine Anomaly Detection](wind-turbine-anomaly-detection/) to learn utilizing these workflows to accelerate your solution development for AI in manufacturing use cases.

