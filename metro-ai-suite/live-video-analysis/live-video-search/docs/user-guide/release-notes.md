# Release Notes: Live Video Search

## Version 2026.2.0

**Release Date**: September 9, 2026

**New**:

- Replaced the legacy `vdms-dataprep` orchestration with backend-neutral `multimodal-dataprep` in Docker Compose and Helm.
- Added an always-on Vector Retriever layer so Video Search no longer accesses a vector database directly.
- Added selectable VDMS (default) and Milvus backends through `VECTORDB_BACKEND` for Compose and `global.vectordbBackend` plus `milvus_override.yaml` for Helm.
- Added pinned standalone Milvus/etcd orchestration and updated build, architecture, device, and deployment guidance for both retriever flavors.
- Replaced the collector/Pipeline Manager WebSocket telemetry path with Metrics Manager for both Docker Compose and Helm, gated by `ENABLE_METRICS_MANAGER` (default `true`) in `setup.sh` and the Makefile. Multimodal DataPrep publishes throughput metrics directly and the UI consumes the same-origin SSE stream through NGINX.
- Added NPU-capable device orchestration for the VSS search stack used by LVS in Docker Compose setup.
- Added `global.accelGroupIds` so the host gids owning `/dev/dri` (GPU) and `/dev/accel` (NPU) are injected into the pod `supplementalGroups`, letting the non-root container open the accelerator device.
- Added a persistent OpenVINO cache (`ovCacheDir`, default `/app/ov_models/ov_cache`) for MME and DataPrep so GPU/NPU model compilation is reused across pod restarts.
- Exposed asynchronous watcher-batch size, polling interval, and timeout settings for Search MS and Smart NVR continuous ingestion through Compose, Helm, and `setup.sh`.
- Added a single, case-insensitive Helm `global.pullPolicy` override for all application images selected through the LVS, VSS, and Smart NVR stack tags.

**Improved**:

- Updated LVS compose deployment to a pure per-component device model (`DATAPREP_EMBEDDING_DEVICE`, `DATAPREP_DETECTION_DEVICE`, `MME_EMBEDDING_DEVICE`; each defaults to `CPU`) and mounted `/dev/accel` for NPU execution. Retired the redundant `VDMS_DATAPREP_DEVICE` baseline.
- Updated LVS Helm deployment templates and values to a pure per-component device model via `global.devices.multimodalEmbedding.*` and `global.devices.multimodalDataprep.{embedding,detection}.*` (each defaults to `CPU`), retiring the legacy `global.gpu.*` block to remove device-configuration ambiguity.
- Removed the ambiguous `ENABLE_EMBEDDING_GPU` shortcut; indexing and query embedding devices are configured independently with `DATAPREP_EMBEDDING_DEVICE` and `MME_EMBEDDING_DEVICE`.
- Renamed the Compose/setup model input from `EMBEDDING_MODEL_NAME` to `MULTIMODAL_EMBEDDING_MODEL`, the DataPrep variables from `VDMS_DATAPREP_*` to `MM_DATAPREP_*`, and `VDMS_PIPELINE_MANAGER_UPLOAD` to `VIDEO_UPLOAD_ENDPOINT`.
- Vector Retriever now waits for a healthy Multimodal Embedding service before starting, using a configurable init check (`embeddingService.waitForHealthy`, `healthUrl`, `healthTimeoutSeconds`, `retryIntervalSeconds`).
- Multimodal DataPrep waits for Metrics Manager readiness when metrics are enabled, and carries component labels for scheduling.
- Made Search MS batch-status polling resilient through `SEARCH_DATAPREP_POLL_MAX_RETRIES`, `SEARCH_DATAPREP_POLL_TIMEOUT_MS`, and `SEARCH_DATAPREP_POLL_RETRY_DELAY_MS`.
- Improved Milvus readiness handling in the Helm deployment.
- Removed the obsolete `vss-collector` subchart, telemetry compose overlay, Telegraf configuration, shared signal PVC, and the pod co-location constraint they required.
- Updated LVS documentation (`get-started`, `deploy-with-helm`, `how-it-works`) with NPU usage guidance, accelerator configuration examples, and Metrics Manager deployment notes.

**Fixed**:

- Fixed Docker Compose backend selection so Milvus deployments do not start or depend on the VDMS service, and stale backend containers are removed when switching backends.
- Corrected the Helm multimodal DataPrep completion-queue default to satisfy the service's minimum queue size and prevent pod startup validation failures.
- Aligned the Helm Multimodal Embedding Serving probe timeout with its Compose healthcheck to avoid one-second startup probe timeouts during model loading.
- Fixed configuration rollouts so a Helm upgrade that changes only ConfigMap values restarts the affected pods; environment variables injected through `envFrom` previously stayed stale until a manual `kubectl rollout restart`.
- Fixed Milvus data persistence so `global.keepPvc=true` also retains the etcd metadata volume; etcd previously used an ephemeral `emptyDir`, which orphaned the retained segment data on pod rescheduling or reinstall.
- Fixed the `nvr-event-router` container healthcheck, which now bypasses proxy settings instead of relying on `curl`.
- Miscellaneous documentation corrections.

## Version 2026.1.0

**Release Date:** June 17, 2026

**New**:

- Deployment with Helm chart.

**Known Issues**:

- First‑time model downloads may take several minutes.
- Time‑range queries require the clock and timezone on the host to be accurate.

## Version 1.0.0

**Release Date**: April 1, 2026

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

**New**:

- Live Video Search stack integrating Smart NVR with VSS Search.
- Time‑range filtering in search via UI or natural‑language query parsing.
- Telemetry visualization in VSS UI for live system performance.

**Known Issues/Limitations**:

- Deploy with Helm is not yet supported for Live Video Search.
- First‑time model downloads may take several minutes.
- Time‑range queries require the clock and timezone on the host to be accurate.

> *The application has been validated on Intel® Xeon® 5 + Intel® Arc&trade; B580 GPU.*
