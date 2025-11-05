# Industrial Edge Insights - Time Series Release Notes

## [v2025.2](TBD) - December 2025

This release introduces substantial enhancements to the Time Series AI stack, including a new sample application and several key features detailed below.

### Time Series AI Stack Enhancements

- Introduced Makefile support for scalable processing of multiple input streams via OPC-UA and MQTT protocols, enabling effective benchmarking of sample applications.
- Updated Makefile to support multiple sample applications through an app parameter.
- Enabled GPU-based inferencing for both Docker Compose and Helm deployments.
- Removed model registry microservice code and documentation from sample applications.
- Integrated nginx reverse proxy to centralize external traffic for web applications and REST API servers, reducing port exposure.
- Refactored configuration files, codebase, and documentation to eliminate redundancy.
- Added documentation for secure connectivity to internal and external MQTT brokers.
- Implemented various improvements in documentation, usability, and configuration management for both Docker Compose and Helm deployments.

### Wind Turbine Anomaly Detection - v1.1.0

- Enabled iGPU based inferencing for the machine learning model using the scikit-learn-intelex package.

### Weld Anomaly Detection - v1.0.0

- Introduced a weld anomaly detection sample application featuring dataset ingestion, CatBoost machine learning model integration, and a dedicated Grafana dashboard.

---

## [v1.0.0](https://github.com/open-edge-platform/edge-ai-suites/commit/cba19ac887b61dd370e563aedb205a8458cf0eea) - August 2025

This is the first version of the Wind Turbine Anomaly detection sample app
showcasing a time series use case by detecting the anomalous power generation patterns
relative to wind speed.

### Deployments

- Docker compose deployment on single node
- Helm deployment on kubernetes single cluster node

### Features

- Added sample OPC-UA server and MQTT publisher data simulators to ingest the wind turbine data
- Generic Time Series AI stack supporting the data ingestion, data analytics,
  data storage and data visualization
- Data Analytics is powered by [Time Series Analytics Microservice](https://docs.openedgeplatform.intel.com/edge-ai-libraries/time-series-analytics/main/user-guide/Overview.html)
  which from the sample app context takes in the configuration related to wind turbine
  sample app and the User Defined Function(UDF) deployment package and provides
  below capabilities:
  - Provides the OPC-UA connector to publish the anomaly alerts to configured
    OPC-UA server
  - Provides support to publish the anomaly alerts to configured MQTT server
  - Provides support to customize the UDF deployment package