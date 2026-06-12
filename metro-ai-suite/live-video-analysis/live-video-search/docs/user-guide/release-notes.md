# Release Notes: Live Video Search

## Upcoming updates (post 2026.1.0)

**Improved**

- Added NPU-capable device orchestration for the VSS search stack used by LVS in Docker Compose setup.
- Updated LVS compose deployment to a pure per-component device model (`DATAPREP_EMBEDDING_DEVICE`, `DATAPREP_DETECTION_DEVICE`, `MME_EMBEDDING_DEVICE`; each defaults to `CPU`) and mount `/dev/accel` for NPU execution. Retired the redundant `VDMS_DATAPREP_DEVICE` baseline; `ENABLE_EMBEDDING_GPU` is now a mode-aware embedding shortcut.
- Updated LVS Helm deployment templates and values to support accelerator mode with `global.gpu.device=GPU|NPU`, including NPU host device mounts and validation updates.
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
