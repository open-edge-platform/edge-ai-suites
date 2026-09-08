# Release Notes

**Release Date**: September 9, 2026

## Version 1.0.0

**New**:

- **Live Video Captioning Integration**: Stream RTSP feeds from any connected camera to the
  Live Video Captioning application (DL Streamer and a VLM). Captions are streamed back to the
  operator dashboard via SSE and overlaid on the WebRTC video player.

- **Loitering Detection Integration**: Route camera feeds to Loitering Detection application. Bounding-box detections are translated from DL Streamer GStreamer
  Video Analytics (GVA) JSON format and pushed back to Nx Witness as analytics objects via the
  Nx REST v4 analytics API.

- **Generic Analytics App API**: A single set of REST routes (`/v1/analytics-apps/{app_id}/…`)
  handles all AI analytics integrations with a consistent lifecycle: start, list, stop, and
  stream results.

- **Provider Dashboard**: React 19 with Vite and Tailwind CSS dashboard served by nginx. Includes
  camera discovery and enable/disable controls, analytics run management, WebRTC live stream
  with caption overlay, and analysis results timeline.

**Validated Versions**:

- Nx Witness: 6.1.2.42921
- Live Video Captioning (LVC): 2026.2.0
- Loitering Detection: 1.6.0

**Known Issues**:

- For fresh integration with Loitering Detection application, the bounding boxes may not render. A workaround is available.

- If the Nx Witness analytics integration is reused from a previous database record (not
  freshly registered), the integration user password is not available from the Nx API. In this
  case, DL Streamer Vision detections cannot be pushed to Nx until the integration is deleted
  from Nx Witness and the VMS Adapter Plugin is restarted to recreate it.

- Helm deployment is not available in this version.
