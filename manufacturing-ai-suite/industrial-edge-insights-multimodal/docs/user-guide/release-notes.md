# Release Notes: Industrial Edge Insights Multimodal

## Version 2026.1

**June 2026**

This release introduces **GPU/NPU hardware acceleration** support for performing inference on DL Streamer P PS, 
**new Classifier ML model for weld time series data analysis enabling support on GPU**,various fixes and documentation improvements.

**New**

- **GPU and NPU Support on DL Streamer Pipeline Server**: Docker Compose and Helm deployments
  now support GPU and NPU acceleration for weld defect classification on the DL Streamer
  Pipeline Server, with updated configuration and user guides for running inference on
  accelerators.
- **GPU Support on Time Series Analytics**: Docker Compose and Helm deployments now support
  GPU acceleration for weld defect classification on the Time Series Analytics microservice, with
  updated configuration and user guides for running inference on GPU.
- **RTSP Camera Configuration Guide**: A new how-to guide has been added for configuring
  an external RTSP camera as the video source for the multimodal sample app.
- **Functional Tests**: Comprehensive functional tests for docker compose and helm deployments
  have been added.

**Improved**

- **New Classifier ML Model**: The weld defect detection pipeline on the Time Series Analytics
  microservice now uses a scikit-learn's (Intel accelerated) RandomForestClassifier model, replacing
  the previous CatBoost model, with optional explanation payloads and updated model artifacts.
- **Renamed Sample App**: "Weld Anomaly Detection" has been renamed to
  "Weld Defect Detection" across all configurations, documentation, and scripts.
- **UDF Package Format**: UDF sample app archives now use tar format instead of zip.
- **Security**: Upgraded to latest available third-party versions in all applicable manifests
- **Documentation**: Time Series vs Multimodal Weld Defect Detection
  distinction clarified and broken references fixed

---

## Version 2026.0

**March 24, 2026**

This release introduces **S3-based frame storage**, **deployment hardening**, and
**documentation improvements**.

**New**

- **RTP Timestamp Alignment**: Fusion Analytics now uses the RTP sender NTP timestamp
  (`metadata.rtp.sender_ntp_unix_timestamp_ns`) to match frames with the nearest metadata
  records for improved synchronization.
- **SeaweedFS S3 Integration**: DL Streamer now stores output frames and images in an
  S3-compatible SeaweedFS backend, with full Helm chart support.
- **Vision Metadata Persistence**: DL pipeline vision metadata is now saved persistently to
  InfluxDB through Fusion Analytics for improved traceability.
- **Helm Deployment**: Helm charts for multimodal deployment are now available.

**Improved**

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

release-notes/release-notes-2025.md
```
hide_directive-->