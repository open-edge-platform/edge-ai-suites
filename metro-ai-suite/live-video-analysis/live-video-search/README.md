# Live Video Search

Live Video Search is a Metro AI Suite sample that adapts the VSS pipeline for semantic search on live Frigate streams. It ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and lets users select cameras, time ranges, and free‑text queries to retrieve ranked, playable clips with confidence scores while surfacing live system metrics.

## Documentation

- **Overview**
  - [Overview](docs/user-guide/index.md): High‑level introduction and navigation.
  - [Architecture](docs/user-guide/overview-architecture-live-video-search.md): End‑to‑end architecture.

- **Getting Started**
  - [Get Started](docs/user-guide/get-started.md): Step‑by‑step setup.
  - [System Requirements](docs/user-guide/system-requirements.md): Hardware and software requirements.

- **Deployment**
  - [Build from Source](docs/user-guide/how-to-build-from-source.md): Build images for the stack.

- **API Reference**
  - [API Reference](docs/user-guide/api-reference.md): Key endpoints and references.

- **Release Notes**
  - [Release Notes](docs/user-guide/release-notes.md): Updates and fixes.

## Notes

- Telemetry is **enabled** for this app and shown in the VSS UI when connected.
- Use Smart NVR UI **Add to Search** to ingest clips into VSS Search.
- Use `source setup.sh --start-usb-camera` to run Frigate with a USB camera input.
