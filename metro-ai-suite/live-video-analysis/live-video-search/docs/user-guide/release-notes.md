# Release Notes: Live Video Search

## Current Version (2026.2.0-ww28)

**July 09, 2026**

**Improved**

- Added NPU-capable device orchestration for the VSS search stack used by LVS in Docker Compose setup.
- Updated LVS compose deployment to a pure per-component device model (`DATAPREP_EMBEDDING_DEVICE`, `DATAPREP_DETECTION_DEVICE`, `MME_EMBEDDING_DEVICE`; each defaults to `CPU`) and mount `/dev/accel` for NPU execution. Retired the redundant `VDMS_DATAPREP_DEVICE` baseline; `ENABLE_EMBEDDING_GPU` is now a mode-aware embedding shortcut.
- Updated LVS Helm deployment templates and values to a pure per-component device model via `global.devices.multimodalEmbedding.*` and `global.devices.vdmsDataprep.{embedding,detection}.*` (each defaults to `CPU`), retiring the legacy `global.gpu.*` block to remove device-configuration ambiguity.
- Added `global.accelGroupIds` so the host gids owning `/dev/dri` (GPU) and `/dev/accel` (NPU) are injected into the pod `supplementalGroups`, letting the non-root container open the accelerator device. Added a persistent OpenVINO cache (`ovCacheDir`, default `/app/ov_models/ov_cache`) for MME and DataPrep so GPU/NPU model compilation is reused across pod restarts.
- Updated LVS documentation (`get-started` and `deploy-with-helm`) with NPU usage guidance and accelerator configuration examples.

## Version 2026.1.0

**June 17, 2026**

**New**

- Deployment with Helm chart.

**Known Issues**

- First‑time model downloads may take several minutes.
- Time‑range queries require the clock and timezone on the host to be accurate.

## Version 1.0.0

**April 01, 2026**

Live Video Search is a new sample application which implements embedding and
visual data ingestion microservices (available in
[Edge AI Libraries](https://docs.openedgeplatform.intel.com/2026.0/ai-libraries.html))
for processing RTSP camera streams and user query-based search. The application
converts the input camera data to embeddings continuously, using models like Clip.
The embeddings are stored in a Vector Database (VectorDB ) and enable search on
live camera feed and historical video data.
A rich UI is provided to configure the camera used for data ingestion, enter
the search query, and view telemetry data, currently, for CPU, GPU, and memory
utilization. The sample application introduces camera streaming with Frigate.

**New**

- Live Video Search stack integrating Smart NVR with VSS Search.
- Time‑range filtering in search via UI or natural‑language query parsing.
- Telemetry visualization in VSS UI for live system performance.

**Known Issues/Limitations**

- Deploy with Helm is not yet supported for Live Video Search.
- First‑time model downloads may take several minutes.
- Time‑range queries require the clock and timezone on the host to be accurate.

> *The application has been validated on Intel® Xeon® 5 + Intel® Arc&trade; B580 GPU.*
