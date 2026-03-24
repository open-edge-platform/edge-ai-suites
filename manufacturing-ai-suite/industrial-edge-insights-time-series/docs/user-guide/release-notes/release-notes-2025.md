# Release Notes: Industrial Edge Insights - Time Series 2025

## Version 2025.2

**December 2025**

This release introduces substantial enhancements to the Time Series AI stack,
including a new sample application and several key features detailed below.

**New**

- Introduced Makefile support for scalable processing of multiple input
  streams via OPC-UA and MQTT protocols, enabling effective benchmarking of
  sample applications.
- Updated Makefile to support multiple sample applications through an app parameter.
- Enabled GPU-based inferencing for both Docker Compose and Helm deployments.
- Integrated nginx reverse proxy to centralize external traffic for web applications
  and REST API servers, reducing port exposure.
- Added documentation for secure connectivity to internal and external MQTT brokers.
- Introduced Weld Anomaly Detection (v1.0.0) sample application featuring dataset
  ingestion, CatBoost machine learning model integration, and a dedicated
  Grafana dashboard.
- Wind Turbine Anomaly Detection - v1.1.0:

  - Enabled iGPU based inferencing for the machine learning model using the
    scikit-learn-intelex package.

**Improved**

- Refactored configuration files, codebase, and documentation to eliminate redundancy.
- Implemented various improvements in documentation, usability, and configuration
  management for both Docker Compose and Helm deployments.
- Removed model registry microservice code and documentation from sample applications.

## Version 1.0.0

**August 2025**

This is
[the first version](https://github.com/open-edge-platform/edge-ai-suites/commit/cba19ac887b61dd370e563aedb205a8458cf0eea)
of the Wind Turbine Anomaly detection sample app showcasing a time series use
case by detecting the anomalous power generation patterns relative to wind speed.

**New**

- Docker compose deployment on single node.
- Helm deployment on Kubernetes single cluster node.
- Added sample OPC-UA server and MQTT publisher data simulators to ingest the
  wind turbine data.
- Generic Time Series AI stack supporting the data ingestion, data analytics,
  data storage and data visualization.
- Data Analytics is powered by
  [Time Series Analytics Microservice](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-libraries/time-series-analytics/index.html)
  which from the sample app context takes in the configuration related to wind
  turbine sample app and the User Defined Function(UDF) deployment package and
  provides below capabilities:
  - Provides the OPC-UA connector to publish the anomaly alerts to configured
    OPC-UA server.
  - Provides support to publish the anomaly alerts to configured MQTT server.
  - Provides support to customize the UDF deployment package.
