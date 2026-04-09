# Release Notes: Pallet Defect Detection 2025

## Version 2.5.0

**December 2025**

**New**

- Consumed the latest DL Streamer Pipeline Server version 2025.2
- Introduced the nginx server as a reverse proxy and TLS.
- Enabled support for GenICam compliant GIGe/USB Cameras using Intel’s gencamsrc
  gStreamer plugin.

**Improved**

- Optimized pipelines and quantized the model from FP32 to INT8.

## Version 2.4.0

**August 2025**

**New**

- Consumed the latest DL Streamer Pipeline Server to 3.1.0.
- Model Registry is now accessed as environment variables.
- Redesigned based on the common application template for Manufacturing AI Suite.

## Version 2.3.0

**April 2025**

**New**

- Consumed the rebranded Edge Video Analytics Microservice as DL Streamer
  Pipeline Server.
- HOST IP where Model Registry Microservice runs is now configurable in
  values.yaml for the Helm chart.
- The GPU parameter that can be set appropriately to utilize underlying GPU is
  available in values.yaml for the Helm chart.

## Version 2.2.0

**March 2025**

**New**

- Architectural changes to include MediaMTX for signaling and Coturn server for
  NAT traversal.
- The WebRTC protocol for streaming the inference output.
- Open Telemetry dashboard for viewing metrics.
- Frame and metadata publishing support over OPCUA protocol.

**Improved**

- The Pallet Defect Detection AI model updated to Geti 2.7.1.
- Updated EVAM image to v2.4.0 and model-registry image to v1.0.3.
- Removed the Visualizer microservice.
- Updated the documentation.

## Version 2.1.0

**March 2025**

**New**

- Added multiple pipelines with gRPC and included the MLOps flow.
- Added documentation for using the model registry and visualization service.

**Improved**

- Updated documentation and configurations across various components.
- Enhanced Helm charts and proxy settings, enabling gRPC communication between
  microservices.
- Implemented Docker and pipeline instruction updates to improve deployment and
  integration processes.

**Fixed**

- Changes to fix the Grafana multiple pipeline issue.

## Version 2.0.0

**February 2025**

**New**

- Added changes to get GPU inference to work in a Kubernetes environment.
- Added S3 usage documentation, including configuration updates in
  evam_config.json and references in the Get Started Guide.

**Improved**

- Migrated pipelines to use gvadetect, including updates to the design diagram
  and documentation.
- Updated PDD documentation adding MRaaS related documentation.
