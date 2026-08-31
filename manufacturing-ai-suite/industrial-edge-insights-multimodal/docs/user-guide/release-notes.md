# Release Notes: Industrial Edge Insights Multimodal

## Version 2026.2

**Release Date**: September 9, 2026

This release introduces **Agentic Integration for user-triggered weld quality monitoring**,
enabling users to initiate analysis for a selected time range. It also introduces a
**standalone Unsloth-based Qwen3.5-2B VLM fine-tuning toolkit** with a weld explainability
LoRA adapter for vLLM-based defect explainability.

The release also includes various bug fixes, security updates, performance improvements, and
documentation enhancements.

**New**:

- **Agentic Integration**: The multimodal sample app now supports an agentic deployment mode,
  with new agent workflow configuration, prompts, policy fallback rules, and a dedicated
  how-to guide for deploying the agent workflow.
- **Qwen VLM Fine-Tuning Toolkit**: A standalone toolkit for fine-tuning Qwen vision-language
  models on weld defect detection has been added, including training, inference, and dataset
  preparation scripts along with a detailed README.
- **vLLM Deployment Path for defect explainability**: A new `docker-compose-vllm.yml` deployment and nginx configuration
  enable running the multimodal sample app with a vLLM-based inference backend, with a
  corresponding how-to guide.
- **Insight-Workbench UI Service**: A new UI service has been added for exploring and analyzing
  weld defect detection results.
- **Multimodal Agentic UI Service**: A new UI service has been added for the agentic
  weld quality analysis workflow. It provides a dashboard for triggering analysis runs,
  monitoring live detection and agent-reasoning phases, and reviewing per-run results including
  policy, analysis, evidence, and ticket agent outputs.

**Improved**:

- **DL Streamer Pipeline Server Naming**: Naming has been aligned across configs and docs to
  consistently distinguish DL Streamer from DL Streamer Pipeline Server.
- **Configuration Cleanup**: Host IP references were replaced with localhost across configuration
  and docs, and references to the deprecated CatBoost model and the model registry were removed.
- **Sample App Cleanup**: The standalone weld-defect-detection sample app was removed in favor of
  the unified multimodal and time-series sample apps.
- **Architecture and Test Workflow**: The architecture diagram and deployment guide were updated,
  and the tests workflow now runs on pushed artifacts.
- **Security**: Addressed SDLe scan findings, applied security-related fixes for vLLM containers,
  and resolved reported vulnerabilities and security-related test failures.
- **Documentation**: Editorial, punctuation, and formatting improvements were made throughout the
  user guide.


## Version 2026.1

**Release Date**: June 17, 2026

This release introduces **GPU/NPU hardware acceleration** support for performing inference on DL Streamer Pipeline Server,
**new Classifier ML model for weld time series data analysis enabling support on GPU**, various fixes and documentation improvements.

**New**:

- **GPU and NPU Support on DL Streamer Pipeline Server**: Docker Compose and Helm deployments
  now support GPU and NPU acceleration for weld defect classification on the DL Streamer
  Pipeline Server, with updated configuration and user guides for running inference on
  accelerators.
- **GPU Support on Time Series Analytics**: Docker Compose and Helm deployments now support
  GPU acceleration for weld defect classification on the Time Series Analytics microservice, with
  updated configuration and user guides for running inference on GPU.
- **RTSP Camera Configuration Guide**: A new how-to guide has been added for configuring
  an external RTSP camera as the video source for the multimodal sample app.
- **Functional Tests**: Comprehensive functional tests for Docker Compose and Helm deployments
  have been added.

**Improved**:

- **New Classifier ML Model**: The weld defect detection pipeline on the Time Series Analytics
  microservice now uses a scikit-learn's (Intel-accelerated) RandomForestClassifier model, replacing
  the previous CatBoost model, with optional explanation payloads and updated model artifacts.
- **UDF Package Format**: UDF sample app archives now use tar format instead of zip.
- **Security**: Upgraded to latest available third-party versions in all applicable manifests.
- **Documentation**: Time Series vs Multimodal Weld Defect Detection
  distinction clarified and broken references fixed.

## Version 2026.0

**Release Date**: March 24, 2026

This release introduces **S3-based frame storage**, **deployment hardening**, and
**documentation improvements**.

**New**:

- **RTP Timestamp Alignment**: Fusion Analytics now uses the RTP sender NTP timestamp
  (`metadata.rtp.sender_ntp_unix_timestamp_ns`) to match frames with the nearest metadata
  records for improved synchronization.
- **SeaweedFS S3 Integration**: DL Streamer now stores output frames and images in an
  S3-compatible SeaweedFS backend, with full Helm chart support.
- **Vision Metadata Persistence**: DL pipeline vision metadata is now saved persistently to
  InfluxDB through Fusion Analytics for improved traceability.
- **Helm Deployment**: Helm charts for multimodal deployment are now available.

**Improved**:

- Simulation data is now embedded directly into the container image, removing the external
  PV/PVC volume dependency and simplifying weld-data-simulator deployment.
- System requirements have been updated to reflect CPU-only validated configurations.
- Third-party service images have been updated: Telegraf, Grafana, Eclipse Mosquitto,
  MediaMTX, Coturn, and SeaweedFS.
- **Security**: SeaweedFS container runtime has been hardened.
- Documentation has been extended and improved for ease of navigation, covering updates to
  setup guides, Helm deployment, and more.

For information on older versions, check [release notes 2025](./release-notes/release-notes-2025.md)

<!--hide_directive
```{toctree}
:maxdepth: 5
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025.md>

```
hide_directive-->
