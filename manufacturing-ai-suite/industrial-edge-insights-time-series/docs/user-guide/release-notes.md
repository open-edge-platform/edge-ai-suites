# Industrial Edge Insights - Time Series Release Notes

## v2025.2 - December 2025

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

<!--hide_directive
:::{toctree}
:hidden:

release-notes/aug-2025

:::
hide_directive-->
