# Live Video Search Overview

Live Video Search is a Metro AI Suite sample that adapts the VSS pipeline for semantic search on live Frigate streams. It ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and lets users select cameras, time ranges, and free‑text queries to retrieve ranked, playable clips with confidence scores while surfacing live system metrics.

## What It Enables

- **Live semantic search** over active camera streams.
- **Time‑range filtering** from either the UI or query parsing (for example, “person seen in last 5 minutes”).
- **Event‑driven ingestion** using Smart NVR + Frigate for clip generation.
- **Unified UI** where VSS Search results appear alongside Smart NVR live context.

## Core Components

Live Video Search combines two existing stacks:

- **Smart NVR** (Metro AI Suite)
  - Frigate NVR ingests live camera streams and emits MQTT events.
  - NVR Event Router brokers event metadata and clip references.
  - Reference UI for Smart NVR management.
  - See Smart NVR docs: [Smart NVR Overview](../../../../smart-nvr/docs/user-guide/index.md)

- **VSS Search Mode** (Edge AI Libraries sample app)
  - Search‑MS + VDMS DataPrep + VDMS VectorDB + Pipeline Manager.
  - VSS UI for semantic queries and clip playback.
  - See VSS docs: [Video Search and Summarization Docs](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/video-search-and-summarization/docs/user-guide/index.md)

## When to Use

- **Operations teams** who need to locate recent events across multiple cameras quickly.
- **Edge deployments** where bandwidth or latency constraints prevent cloud‑first analytics.
- **Safety and compliance** scenarios requiring rapid retrieval of recent footage.

## Key Behaviors

- **Smart NVR‑initiated ingestion** sends selected clips directly to VSS Search.
- **Time‑range filters** reduce search scope and improve relevance.
- **Telemetry** provides real‑time system metrics in the VSS UI.
