# How It Works

This document describes the end‑to‑end architecture of Live Video Search and how NVR Event Router and VSS Search integrate.

## High‑Level Architecture

```mermaid
graph TD
  A[Camera Streams] -->|RTSP/Video Feeds| B[Frigate NVR]
  B -->|Event Clips + Metadata| C[NVR Event Router]
  C -->|Watched camera ingestion| H[Pipeline Manager]
  H --> D[Multimodal DataPrep]
  D --> G[VDMS or Milvus VectorDB]
  H --> E[VSS Search‑MS]
  E --> R[Vector Retriever]
  R --> G
  R --> M[Multimodal Embedding Serving]
  H --> I[VSS UI Configure Cameras and Search]
  K[Telemetry Collector] --> H
```

## Data Flow

1. **Ingestion**: Cameras stream into Frigate, which records clips and publishes events via MQTT.
2. **Event Routing**: NVR Event Router receives events and associates clips with camera metadata.
3. **Indexing**: VSS camera configuration enables watcher-based clip ingestion to Pipeline Manager, which forwards clips to Multimodal DataPrep. DataPrep creates embeddings in-process and stores them in the selected VDMS or Milvus backend.
4. **Querying**: Users query VSS UI with optional time‑range filters. Search‑MS sends vector similarity queries to Vector Retriever, which embeds the query through Multimodal Embedding Serving and reads the selected vector database. Search‑MS then aggregates and ranks the matching clips.
5. **Visualization**: Results are shown directly in VSS UI.
6. **Telemetry**: Collector streams system metrics to Pipeline Manager and the UI.

## Integration Points

- **Watcher-based ingestion path** ties enabled camera clips directly to VSS Search input.
- **Pipeline Manager endpoints** unify search configuration and retrieval.
- **Backend-neutral retrieval** keeps Search‑MS independent of VDMS and Milvus through the Vector Retriever API.
- **Telemetry WS** provides live metrics for operational visibility.

## Related Architecture References

- [Smart NVR How It Works](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/smart-nvr/index.html#how-it-works)
- [Video Search and Summarization Architecture](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/video-search-and-summarization/how-it-works/video-search-and-summarization.html)
