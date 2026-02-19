# Live Video Search

<!--hide_directive
<div class="component_card_widget">
	<a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/live-video-analysis/live-video-search">
		 GitHub project
	</a>
	<a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/live-video-analysis/live-video-search/README.md">
		 Readme
	</a>
</div>
hide_directive-->


**Live Video Search** is a Metro AI Suite sample that adapts the VSS pipeline for semantic search on live Frigate streams. The application ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and enables you to select cameras, time ranges, and free-text queries. You can retrieve ranked, playable clips with confidence scores and view live system metrics.


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

## Documentation

- **Get Started**
  - [Get Started](./get-started.md): Deploy the full stack locally.
  - [System Requirements](./system-requirements.md): Hardware and software prerequisites.

- **How It Works**
  - [Architecture](./overview-architecture-live-video-search.md): End‑to‑end architecture and data flow.

- **Deployment**
  - [Build from Source](./how-to-build-from-source.md): Build the required images.

- **Usage & API**
  - [API Reference](./api-reference.md): Key endpoints and references.

- **Release & Support**
  - [Release Notes](./release-notes.md): Updates and fixes.

<!--hide_directive
:::{toctree}
:maxdepth: 2
:hidden:

get-started
system-requirements
how-it-works
how-to-build-from-source
api-reference
release-notes
troubleshooting
:::
hide_directive-->
