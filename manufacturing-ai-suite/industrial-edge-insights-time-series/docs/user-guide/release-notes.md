# Release Notes: Industrial Edge Insights - Time Series

## Version 2026.2

**Release Date**: September 9, 2026

This release removes the deprecated **Weld Defect Detection sample app**, adds **ViPPET
integration** for deploying the Time Series Analytics Microservice, aligns naming for
**DL Streamer / DL Streamer Pipeline Server**, and includes **security hardening** along with
various fixes and documentation improvements.

**New**:

- **ViPPET Integration**: The Time Series Analytics Microservice can now be deployed as part
  of the Visual Pipeline and Platform Evaluation Tool (ViPPET) stack.

**Improved**:

- **Weld Defect Detection Sample App Removed**: As previously announced, the deprecated Weld
  Defect Detection Time Series sample app, its training scripts, models, simulation data, and
  documentation have been removed from the repository.
- **DL Streamer Naming Alignment**: Updated references across configuration, documentation,
  and test utilities to align with the DL Streamer / DL Streamer Pipeline Server naming.
- **Model Registry and CatBoost References Removed**: Removed remaining model registry
  configuration references and CatBoost mentions from deployment manifests, tests, and
  documentation, aligning with the current scikit-learn RandomForestClassifier-based workflow.
- **Container Image and Helm Chart Updates**: Bumped Telegraf, Grafana, and NGINX image
  versions in Docker Compose deployments, and updated the Helm chart/appVersion and
  `IMAGE_SUFFIX` to the 2026.2.0 release line.
- **Localhost Access and Reduced MQTT Exposure**: Replaced `<host_ip>` placeholders with
  `localhost` in user guides and reduced MQTT port exposure in Helm/nginx configuration.
- **Security**: Bumped aiohttp and cryptography dependencies to address reported
  vulnerabilities, fixed Bandit `shell=True` (B602) findings and CodeQL alerts by removing
  credential logging, applied SDLe scan remediations with justified `# nosec` annotations, and
  upgraded to the latest available third-party versions in all applicable manifests.
- **Documentation**: Multiple language, formatting, and editorial fixes applied across the
  Time Series user guides.


## Version 2026.1

**Release Date**: June 17,2026

This release introduces **batch processing UDFs**, **a new ML model for Weld Defect Detection**,
**scikit-learn training scripts for Weld Defect Detection**, and various fixes and documentation
improvements.

**Deprecated**: The Weld Defect Detection Time Series Sample App is deprecated and will be removed in the 2026.2 release.

**New**:

- **Batch Processing UDFs**: Batch-mode UDF variants for both Wind Turbine Anomaly
  Detection and Weld Defect Detection are now available, including Kapacitor TICK
  scripts, per-app `config-batch.json`, and `make batch` support for running
  Kapacitor windowed batches. This is enabled primarily for the benchmarking exercise.
- **Weld Defect Detection Training Scripts**: Classification training and inference
  scripts using a scikit-learn (Intel-accelerated) pipeline have been added for the
  Weld Defect Detection sample app.
- **Functional Tests**: Comprehensive functional tests for Docker Compose and Helm deployments have been added.
- **GPU Support for Weld Defect Detection**: Docker Compose and Helm deployments now support
  GPU acceleration for weld defect detection on the Time Series Analytics microservice image, with
  updated configuration and user guides for running inference on GPU.

**Improved**:

- **Wind Turbine Anomaly Detection ML Model**: The LinearRegression model has been removed
  from the Wind Turbine Anomaly Detection sample app; RandomForestRegressor (Intel® Extension
  for Scikit-learn) is now the only inference model, with updated training scripts and
  adjusted anomaly scoring thresholds.
- **Weld Defect Detection ML Model**: Weld Defect Detection now uses a
  scikit-learn (Intel-accelerated) classifier model, replacing the previous CatBoost
  classifier, with updated training scripts and model artifacts.
- **Renamed Sample App**: "Weld Anomaly Detection" has been renamed to
  "Weld Defect Detection" across all configurations, documentation, and scripts.
- **UDF Deployment Package Format**: User Defined Function deployment package format for the sample apps will be generated in
  tar format and used to configure Time Series Analytics microservice.
- **Security**: Upgraded to latest available third-party versions in all applicable manifests.
- **Documentation**: Time Series vs Multimodal Weld Defect Detection
  distinction clarified, Weld Defect Detection docs updated for GPU usage, OPC-UA
  alert configuration docs updated, broken references and typos fixed.

## Version 2026.0

**Release Date**: March 2026

This release introduces **new documentation for UDF development and wind turbine
model integration**, along with **updated service images** and
**documentation improvements**.

**New**:

- **UDF Development Guide** — Added a comprehensive guide for writing
  User Defined Functions (UDFs) covering architecture, implementation steps, and
  examples.
- **Wind Turbine Model Guidelines** — Added wind turbine model selection and
  integration guidelines.

**Improved**:

- Updated image tags/versioning and aligned deployment/documentation examples.
- Updated third-party service image versions used by Time Series (Telegraf,
  Grafana, Eclipse Mosquitto).
- Reorganized Time Series how-to guides for better navigation.
- Updated Time Series documentation toctree structure.
- Fixed failing code blocks in Time Series documentation.
- Fixed formatting issues in Wind Turbine Anomaly documentation.

<!--hide_directive
```{toctree}
:hidden:
Release Notes 2025 <./release-notes/release-notes-2025>
```
hide_directive-->
