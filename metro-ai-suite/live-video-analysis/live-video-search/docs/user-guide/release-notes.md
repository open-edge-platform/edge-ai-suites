# Release Notes: Live Video Search

## Current Version (2026.2.0-ww31)

**July 28, 2026**

**Improved**

- Replaced the legacy collector/Pipeline Manager WebSocket telemetry path with
  Metrics Manager for both Docker Compose and Helm. Multimodal DataPrep now
  publishes throughput metrics directly, the UI consumes the same-origin SSE
  stream through NGINX, and the obsolete shared signal PVC and pod co-location
  constraint were removed.
- Replaced the legacy `vdms-dataprep` orchestration with backend-neutral `multimodal-dataprep` in Docker Compose and Helm.
- Added an always-on Vector Retriever layer so Video Search no longer accesses a vector database directly.
- Added selectable VDMS (default) and Milvus backends through `VECTORDB_BACKEND` for Compose and `global.vectordbBackend` plus `milvus_override.yaml` for Helm.
- Added pinned standalone Milvus/etcd orchestration and updated build, architecture, device, and deployment guidance for both retriever flavors.
- Removed the ambiguous `ENABLE_EMBEDDING_GPU` shortcut; indexing and query embedding devices are configured independently with `DATAPREP_EMBEDDING_DEVICE` and `MME_EMBEDDING_DEVICE`.
- Renamed the Compose/setup model input from `EMBEDDING_MODEL_NAME` to `MULTIMODAL_EMBEDDING_MODEL`.
- Exposed asynchronous watcher-batch size, polling interval, and timeout
  settings for Search MS and Smart NVR continuous ingestion through Compose,
  Helm, and `setup.sh`.
- Fixed Docker Compose backend selection so Milvus deployments do not start or
  depend on the VDMS service, and stale backend containers are removed when
  switching backends.
- Corrected the Helm multimodal DataPrep completion-queue default to satisfy
  the service's minimum queue size and prevent pod startup validation failures.
- Added a single, case-insensitive Helm `global.pullPolicy` override for all
  application images selected through the LVS, VSS, and Smart NVR stack tags.
- Aligned the Helm Multimodal Embedding Serving probe timeout with its Compose
  healthcheck to avoid one-second startup probe timeouts during model loading.

## Version 2026.2.0-ww28

**July 09, 2026**

**Improved**

- Added NPU-capable device orchestration for the VSS search stack used by LVS in Docker Compose setup.
- Updated LVS compose deployment to a pure per-component device model (`DATAPREP_EMBEDDING_DEVICE`, `DATAPREP_DETECTION_DEVICE`, `MME_EMBEDDING_DEVICE`; each defaults to `CPU`) and mount `/dev/accel` for NPU execution. Retired the redundant `VDMS_DATAPREP_DEVICE` baseline; `ENABLE_EMBEDDING_GPU` is now a mode-aware embedding shortcut.
- Updated LVS Helm deployment templates and values to a pure per-component device model via `global.devices.multimodalEmbedding.*` and `global.devices.multimodalDataprep.{embedding,detection}.*` (each defaults to `CPU`), retiring the legacy `global.gpu.*` block to remove device-configuration ambiguity.
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
