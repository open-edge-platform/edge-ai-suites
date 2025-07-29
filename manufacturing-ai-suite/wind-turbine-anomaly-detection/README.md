# Wind Turbine Anomaly Detection Sample Application

Wind Turbine Anomaly Detection sample application demonstrates a time series use case by detecting the anomalous power generation patterns relative to wind speed. By identifying deviations, it helps optimize maintenance schedules and prevent potential turbine failures, enhancing operational efficiency.

## Get Started

To see the system requirements and other installation, see the following guides:

  - [System Requirements](docs/user-guide/system-requirements.md): Hardware and software requirements for running the sample application.
  - [Get Started](docs/user-guide/get-started.md): Step-by-step guide to getting started with the docker compose deployment of the sample application.

## Architecture and Functionality Overview

The Wind Turbine Anomaly Detection sample application comprises of data simulators, the generic Time Series AI stack based on **TICK Stack**, and Grafana. The Model Registry microservice helps to achieve the MLOps flow by uploading the **UDF deployment package**.

![Time Series AI Stack Architecture Diagram](./docs/user-guide/_images/time-series-ai-stack-architecture.png)

  - **Data Simulators/Destinations**: OPC-UA server and MQTT Publisher simulate data sources and destinations, reading from CSV files and interfacing with Telegraf plugins for data ingestion.
  - **Generic Time Series AI Stack**: A customizable pipeline for data ingestion, storage, processing, and visualization, supporting integration with various databases, and enabling deep learning model execution.
  - **Data Ingestion**: Telegraf collects and reports metrics using input plugins, sending ingested data to InfluxDB for storage.
  - **Data Storage**: InfluxDB is a high-performance database optimized for time series data, supporting high write throughput and efficient querying.
  - **Data Processing**: Kapacitor processes time series data in real-time, allowing custom logic using User-Defined Functions (UDFs) for anomaly detection and advanced analytics.
  - **Data Visualization**: Grafana offers an intuitive interface for real-time visualization of time series data stored in InfluxDB, enabling custom dashboards and monitoring.

For more details on Architecture, see [How it works](docs/user-guide/how-it-works.md).

## Learn More

  - [How to Deploy with Helm](docs/user-guide/how-to-deploy-with-helm.md): Guide for deploying the sample application on a k8s cluster using Helm.
  - [How to build from source and deploy](docs/user-guide/how-to-build-from-source.md): Guide to build from source and docker compose deployment
  - [How to configure OPC-UA/MQTT alerts](docs/user-guide/how-to-configure-alerts.md): Guide for configuring the OPC-UA/MQTT alerts in the Time Series Analytics microservice
  - [How to configure custom UDF deployment package](docs/user-guide/how-to-configure-custom-udf.md): Guide for deploying a customized UDF deployment package (udfs/models/tick scripts)
  - [How to create a new sample app](docs/user-guide/how-to-create-a-new-sample-app.md): Guide for creating a new sample app by referencing Wind Turbine Anomaly Detection sample app
- **Release Notes**
  - [Release Notes](docs/user-guide/release_notes/Overview.md): Information on the latest updates, improvements, and bug fixes.


