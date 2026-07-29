# Release Notes

- [Version 1.0.0](#version-100)

Details about the changes and known issues in each release of the VMS Adapter Plugin.

## Current Release

### Version 1.0.0

**Release Date**: *TBD*

**New Features**:

- **Multi-VMS Support**: Connect  Nx Witness (REST v4) and Frigate (0.15) cameras simultaneously from a single plugin instance. Camera IDs are vendor-prefixed (`frigate:*`, `nx:*`) to ensure uniqueness across systems.

- **Live Video Captioning Integration**: Stream RTSP feeds from any connected camera to the Intel Live Video Captioning application (DLStreamer + VLM). Captions are streamed back to the operator dashboard via SSE and overlaid on the WebRTC video player.

- **DLStreamer Vision Integration**: Route camera feeds to a DLStreamer Pipeline Server for warehouse defect detection. Bounding-box detections are translated from DLStreamer GVA JSON format and pushed back to Nx Witness as analytics objects via the Nx REST v4 analytics API.

- **Dynamic Schema Forms**: The operator dashboard renders analytics configuration forms directly from each Analytics App's live OpenAPI schema. No frontend changes are required when Analytics App parameters change.

- **Generic Analytics App API**: A single set of REST routes (`/v1/analytics-apps/{app_id}/…`) handles all AI analytics integrations with a consistent lifecycle: start, list, stop, and stream results.

- **Provider Dashboard**: React 19 + Vite + Tailwind CSS dashboard served by nginx. Includes camera discovery and enable/disable controls, analytics run management, WebRTC live stream with caption overlay, and analysis results timeline.

- **PostgreSQL Persistence**: Camera registrations, analytics sessions, and metadata events are stored in a PostgreSQL 15 database via async SQLAlchemy 2.

- **Docker Compose Deployment**: Full stack in four services — `vms-backend`, `vms-ui` (nginx), `postgres`, and `frigate`.

**Known Issues**:

- If the Nx Witness analytics integration is reused from a previous database record (not freshly registered), the integration user password is not available from the Nx API. In this case, DLStreamer Vision detections cannot be pushed to Nx until the integration is deleted from Nx Witness and VAP is restarted to recreate it.

- Helm deployment is not available in this version.
