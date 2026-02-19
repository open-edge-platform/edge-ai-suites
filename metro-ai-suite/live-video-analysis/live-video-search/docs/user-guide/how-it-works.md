# How It Works

This document describes the end‑to‑end architecture of Live Video Search and how Smart NVR and VSS Search integrate.

## High‑Level Architecture

```mermaid
graph TD
  A[Camera Streams] -->|RTSP/Video Feeds| B[Frigate NVR]
  B -->|Event Clips + Metadata| C[NVR Event Router]
  C -->|Add to Search| H[Pipeline Manager]
  H --> E[VSS Search‑MS]
  E --> F[VDMS DataPrep]
  F --> G[VDMS VectorDB]
  H --> I[VSS UI]

  C --> J[Smart NVR UI]

  K[Telemetry Collector] --> H
```

## Data Flow

1. **Ingestion**: Cameras stream into Frigate, which records clips and publishes events via MQTT.
2. **Event Routing**: NVR Event Router receives events and associates clips with camera metadata.
3. **Indexing**: Smart NVR sends selected clips to Pipeline Manager, which forwards them to DataPrep. Embeddings are stored in VDMS.
4. **Querying**: Users query VSS UI with optional time‑range filters. Search‑MS retrieves and ranks relevant clips.
5. **Visualization**: Results are shown in VSS UI while Smart NVR UI remains available for live context.
6. **Telemetry**: Collector streams system metrics to Pipeline Manager and the UI.

## Integration Points

- **Smart NVR upload path** ties selected clips directly to VSS Search input.
- **Pipeline Manager endpoints** unify search configuration and retrieval.
- **Telemetry WS** provides live metrics for operational visibility.

## Related Architecture References

- Smart NVR architecture: [Smart NVR Overview](../../../../smart-nvr/docs/user-guide/index.md)
- VSS Search architecture: [Video Search and Summarization Docs](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/video-search-and-summarization/docs/user-guide/overview-architecture-search.md)
