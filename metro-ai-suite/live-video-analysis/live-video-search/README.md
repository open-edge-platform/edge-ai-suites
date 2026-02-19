# Live Video Search

**Live Video Search** is a Metro AI Suite sample that adapts the VSS pipeline for semantic search on live Frigate streams. It ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and lets users select cameras, time ranges, and free‑text queries to retrieve ranked, playable clips with confidence scores while surfacing live system metrics.

## Get Started

To see the system requirements and other installations, see the following guides:

  - [Get Started](docs/user-guide/get-started.md): Step‑by‑step setup.
  - [System Requirements](docs/user-guide/system-requirements.md): Hardware and software requirements.

## How It Works

The diagram shows how video moves from cameras to searchable results and live monitoring. It highlights the main components involved in capturing events, processing clips, and presenting results to users. Each step builds on the previous one to keep video searchable, observable, and easy to use.

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

## Learn More

  - [Architecture](docs/user-guide/overview-architecture-live-video-search.md): End‑to‑end architecture.
  - [System Requirements](docs/user-guide/system-requirements.md): Hardware and software requirements.
  - [Build from Source](docs/user-guide/how-to-build-from-source.md): Build images for the stack.
  - [API Reference](docs/user-guide/api-reference.md): Key endpoints and references.
  - [Release Notes](docs/user-guide/release-notes.md): Updates and fixes.

## Notes

- Telemetry is **enabled** for this app and shown in the VSS UI when connected.
- Use Smart NVR UI **Add to Search** to ingest clips into VSS Search.
- Use `source setup.sh --start-usb-camera` to run Frigate with a USB camera input.
