# Release Notes

## v2.3.0 (April 2025)

### Updates
- Consumed rebranded Edge Video Analytics Microservice as DL Streamer Pipeline Server.
- HOST IP where Model Registry Microservice runs is now configurable in values.yaml of helm chart.
- GPU parameter that can be set appropriately to utilize underlying GPU is available in values.yaml of helm chart.

---

## v2.2.0 (March 2025)

### Added
- Architectural changes to include MediaMTX for signaling and Coturn server for NAT traversal. Removed Visualizer microservice.
- WebRTC protocol for streaming the inference output.
- Open Telemetry dashboard for viewing metrics.
- Frame and metadata publishing support over OPCUA protocol.

### Updates
- Pallet Defect Detection AI model updated to Geti 2.7.1
- Updated EVAM image to v2.4.0 and model-registry image to v1.0.3.
- Updated documentation.

---

## v2.1.0 (March 2025)

### Added
- Added changes to get GPU inference to work in a Kubernetes environment.
- Added S3 usage documentation, including configuration updates in evam_config.json and references in the Get Started Guide.

### Fixed
- Migrated pipelines to use gvadetect, including updates to the design diagram and documentation.

### Updates
- Updated PDD documentation adding MRaaS related documentation.

---

## v2.0.0 (February 2025)

### Added
- Added multiple pipelines with gRPC and included MLOps flow.
- Added documentation for using the model registry and visualization service.

### Fixed
- Changes to fix Grafana multiple pipeline issue.

### Updates
- Updated documentation and configurations across various components.
- Enhanced helm charts and proxy settings, enabling gRPC communication between microservices.
- Implemented Docker and pipeline instruction updates to improve deployment and integration processes.
