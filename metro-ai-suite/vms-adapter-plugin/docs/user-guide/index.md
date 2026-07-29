<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/vms-adapter-plugin">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/vms-adapter-plugin/README.md">
     Readme
  </a>
</div>
hide_directive-->

# VMS Adapter Plugin Overview

The VMS Adapter Plugin (VAP) is an I/O bridge between Video Management Systems (VMS) and AI Analytics Apps. It is designed to help developers understand how to connect existing VMS infrastructure to AI analytics pipelines, manage camera streams through a unified provider dashboard, and extend the system with new VMS vendors or analytics applications.

## Overview

The **VMS Adapter Plugin** connects VMS solutions like Nx Witness, Genetec, Milestone, and Frigate cameras to AI analytics
applications such as Live Video Captioning and DLStreamer Vision based Loitering Detection, and presents a unified React provider dashboard for discovering cameras, managing analytics runs, and viewing live results. Adding support for a new VMS or a new Analytics App requires only a new shim class — no route changes are needed.

### Example Use Cases

- **Intelligent Surveillance**: Connect IP cameras from Nx Witness to Live Video Captioning for scene description and prompt-driven monitoring (for example, "Is there an unauthorized person in the area?").
- **Warehouse Quality Control**: Route camera feeds from Frigate or Nx Witness to DLStreamer Vision application and automatically push detected defect bounding boxes back into Nx Witness for operator review.
- **Multi-Camera Analytics Management**: Discover all cameras from all connected VMS systems in one dashboard and selectively enable AI analytics on specific cameras without reconfiguring each system individually.

### Key Benefits

- **Multi-VMS Support**: Connect cameras from Nx Witness and Frigate simultaneously from a
  single plugin instance.
- **Pluggable Analytics Apps**: AI analytics applications plug in as shims. New apps require no route changes — just a new shim class registered in `factory.py`.
- **Dynamic Schema Forms**: The dashboard renders analytics configuration forms directly from each Analytics App's live OpenAPI schema — no frontend changes are needed when parameters change.
- **Generic Analytics App API**: A single set of REST routes (`/v1/analytics-apps/{app_id}/…`) handles all integrations with a consistent lifecycle (start, list, stop, stream results).
- **Provider Dashboard**: React-based UI for discovering cameras, enabling/disabling streams, configuring analytics parameters, and viewing live results.

## Sequence Diagram


![VAP Sequence Diagram](./_assets/vap-sequence-diagram.svg)

The VMS Adapter Plugin lifecycle consists of two phases: manual setup and a continuous processing loop.

**Setup**

Before the plugin can run, three components must be started manually: the Video Management System (VMS), the Analytics Application, and the plugin itself. The VMS serves as the source of camera streams and as the sink for inference results. The Analytics Application hosts the inference pipeline. The plugin acts as the integration bridge between the two.

**Processing Loop**

Once all components are running, the VMS Adapter Plugin initiates the processing loop:

1. The plugin queries the VMS for the RTSP stream URL and associated camera parameters (e.g., stream ID, resolution, metadata).
2. The VMS returns the RTSP URL and parameters to the plugin.
3. The plugin uses these parameters to trigger the inference pipeline in the Analytics Application, passing the RTSP URL directly so the Analytics App can connect to the camera stream independently — frames are never relayed through the plugin.
4. The Analytics Application connects directly to the VMS RTSP stream and receives video frames continuously.
5. For each frame, the Analytics Application runs inference to produce detections (object bounding boxes, labels) or captions depending on the configured pipeline.
6. The inference results are returned to the plugin.
7. The plugin pushes the detections or captions back to the VMS server.
8. The VMS server forwards the results to the VMS Client UI for display.

## How it Works

The VMS Adapater Plugin is a modular orchestration service. VMS shims discover cameras from their respective systems and provide RTSP URLs. Analytics App shims manage run lifecycle and result delivery. The FastAPI backend coordinates between shims, persists state to PostgreSQL, and exposes a unified API consumed by the React provider dashboard.

```
VMS Systems
  ┌──────────┐   RTSP / REST    ┌───────────────────────────────────────────┐
  │ Any VMS  ├─────────────────►│                                           │
  └──────────┘                  │           VMS Adapter Plugin              │
  ┌──────────┐   RTSP / REST    │                                           │
  │Nx Witness├─────────────────►│  FastAPI Backend    ┌───────────────────┐ │
  └──────────┘                  │  ─────────────      │  PostgreSQL DB    │ │
                                │  Orchestrator   ◄──►│  (cameras,        │ │
                                │  Camera sync        │   sessions,       │ │
                                │  Schema fetch       │   events)         │ │
                                │                     └───────────────────┘ │
                                └────────┬─────────────────────┬────────────┘
                                         │                     │
                          ┌──────────────▼──────┐   ┌─────────▼──────────────┐
                          │  Live Video         │   │  Loitering Detetcion   │
                          │  Captioning (LVC)   │   │  (DLS vision) App      │
                          └──────────┬──────────┘   └────────────┬───────────┘
                                     │                           │
                          ┌──────────▼───────────────────────────▼─────────┐
                          │              Provider Dashboard (React)        │
                          │   Camera list | Run controls | Live stream     │
                          └────────────────────────────────────────────────┘
```

To interact with plugin, there are two dashboards available as option to the user. The first option is to use the respective VMS UI which will have an integration with VAP. This option is provided by default but comes with whatever limitation the respective VMS UI may have. One example is the limited support to integrate rich NLQ metadata coming from the GenAI pipeline based applications. The other option is a Analytics provider UI (say, ISV) which gives a consolidated view across all cameras and analytics. It internally synchronizes with the VMS UI as required. In the documentation, the former will be referred to as VMS UI and the latter as Provider UI.

See [How It Works](./how-it-works.md) for a detailed breakdown of data flows, component
descriptions, and extension points.

### Key Features

- **Feature 1**: Multi-VMS architecture with a pluggable shim model enables adding new VMS
  vendors without modifying core routes.
- **Feature 2**: Connects to AI analytics pipelines — Live Video Captioning (DLStreamer + VLM)
  and Loitering Detection (DLStreamer Pipeline Server) — through the generic Analytics App
  shim interface.
- **Feature 3**: React provider dashboard dynamically renders analytics forms from each
  Analytics App's live OpenAPI schema, requiring no UI changes when app parameters evolve.
- **Feature 4**: DLStreamer Vision results are translated from DLStreamer GVA JSON
  format and pushed back to Nx Witness as analytics objects (bounding boxes with labels),
  visible directly in the Nx Witness Desktop Client.

## Learn More

- [Get Started](./get-started.md): Follow step-by-step instructions to deploy and run the
  application.
- [System Requirements](./get-started/system-requirements.md): Check the hardware and
  software requirements.
- [Build from Source](./get-started/build-from-source.md): Build and deploy the application
  from source using Docker Compose.
- [Deploy with Helm](./get-started/deploy-with-helm.md): Deploy the application with Helm.
- [How It Works](./how-it-works.md): Detailed architecture, data flows, and component
  descriptions.
- [How-To Guides](./how-to-guides.md): End-to-end tutorials for Live Video Captioning and
  DLStreamer Vision integrations.
- [API Reference](./api-reference.md): Comprehensive reference for the available REST API
  endpoints.
- [Troubleshooting](./troubleshooting.md): Find solutions to common issues.
- [Release Notes](./release-notes.md): Latest updates, improvements, and known issues.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
how-to-guides
api-reference
troubleshooting
release-notes

:::
hide_directive-->
