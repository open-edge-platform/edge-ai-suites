# VMS Adapter Plugin

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.2.0/metro-ai-suite/vms-adapter-plugin">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/metro-ai-suite/vms-adapter-plugin/README.md">
     Readme
  </a>
</div>
hide_directive-->

The VMS Adapter Plugin (VAP) is an I/O bridge between Video Management Systems (VMS) and AI
Analytics Applications. It helps developers understand how to connect existing VMS infrastructure to AI
analytics pipelines, manage camera streams through a unified provider dashboard, and extend the
system with new VMS vendors or analytics applications.

## Overview

The **VMS Adapter Plugin** connects VMS solutions like Nx Witness, Genetec, and Milestone to
AI analytics applications such as Live Video Captioning and DL Streamer Vision-based Loitering
Detection, and presents a unified React provider dashboard for discovering cameras, managing
analytics runs, and viewing live results. Adding support for a new VMS or a new Analytics
Application requires only a new shim class — no route changes are needed.

### Example Use Cases

- **Intelligent Surveillance**: Connect IP cameras from Nx Witness to Live Video Captioning
  for scene description and prompt-driven monitoring (for example, "Is there an unauthorized
  person in the area?").
- **Warehouse Quality Control**: Route camera feeds from Nx Witness to DL Streamer Vision
  application and automatically push detected defect bounding boxes back into Nx Witness for
  operator review.
- **Multi-Camera Analytics Management**: Discover all cameras from all connected VMS systems
  in one dashboard and selectively enable AI analytics on specific cameras without reconfiguring
  each system individually.

### Key Benefits

- **Multi-VMS Support**: Connect cameras from supported VMS systems such as Nx Witness through a
  single plugin instance.
- **Pluggable Analytics Applications**: AI analytics applications plug in as shims. New
  applications require no route changes — just a new shim class registered in `factory.py`.
- **Dynamic Schema Forms**: The dashboard renders analytics configuration forms directly from
  each Analytics App's live OpenAPI schema — no frontend changes are needed when parameters
  change.
- **Generic Analytics App API**: A single set of REST routes
  (`/v1/analytics-apps/{app_id}/…`) handles all integrations with a consistent lifecycle (start,
  list, stop, and stream results).
- **Provider Dashboard**: React-based UI for discovering cameras,
  enabling/disabling streams, configuring analytics parameters, and viewing live results.

## Sequence Diagram

![VAP Sequence Diagram](./_assets/VAP-sequence-diagram.svg)

The VMS Adapter Plugin lifecycle consists of two phases: manual setup and a continuous
processing loop.

**Setup**:

For the plugin to run, start these three components manually: the VMS, the Analytics Application,
and finally the plugin itself. The VMS serves as the source of camera streams and as the sink for
inference results. The Analytics Application hosts the inference pipeline. The plugin acts as the
integration bridge between the two.

**Processing Loop**:

Once all components are running, the VMS Adapter Plugin initiates the processing loop:

1. The plugin queries the VMS for the Real-Time Streaming Protocol (RTSP) stream URL and
   associated camera parameters (e.g., stream ID, resolution, metadata).
2. The VMS returns the RTSP URL and parameters to the plugin.
3. The plugin uses these parameters to trigger the inference pipeline in the Analytics
   Application, passing the RTSP URL directly so the Analytics App can connect to the camera
   stream independently — the plugin never relays frames.
4. The Analytics Application connects directly to the VMS RTSP stream and receives video frames
   continuously.
5. For each frame, the Analytics Application runs inference to produce detections (object
   bounding boxes, labels) or captions depending on the configured pipeline.
6. The Analytics Application returns the inference results to the plugin.
7. The plugin pushes the detections or captions back to the VMS server.
8. The VMS server forwards the results to the VMS Client UI for display.

## How it Works

The VMS Adapter Plugin is a modular orchestration service. VMS shims discover cameras from their
respective systems and provide RTSP URLs. Analytics App shims manage run lifecycle and result
delivery. The FastAPI backend coordinates between shims, persists state to a PostgreSQL database,
and exposes a unified API consumed by the React provider dashboard.

![VAP System Architecture Diagram](./_assets/VAP-System-Architecture-frame.svg)

To interact with the plugin, users have two dashboard options. The first option is to use the
respective VMS UI, which integrates with VAP. The plugin provides this option by default, but it
comes with whatever limitation the respective VMS UI may have. One example is the limited support
to integrate rich Natural Language Query (NLQ) metadata coming from the Generative AI (GenAI)
pipeline based applications. The other option is an Analytics provider UI, like an Independent
Software Vendor (ISV), which gives a consolidated view across all cameras and analytics. It
internally synchronizes with the VMS UI as required. This documentation refers to the former as
the VMS UI and to the latter as the Provider UI.

See [How It Works](./how-it-works.md) for a detailed breakdown of data flows, component
descriptions, and extension points.

### Key Features

- **Feature 1**: Multi-VMS architecture with a pluggable shim model enables adding new VMS
  vendors without modifying core routes.
- **Feature 2**: Connects to AI analytics pipelines — Live Video Captioning (DL Streamer and
  a Vision-Language Model) and Loitering Detection (DL Streamer Pipeline Server) — through the
  generic Analytics Application shim interface.
- **Feature 3**: React provider dashboard dynamically renders analytics forms from each
  Analytics App's live OpenAPI schema, requiring no UI changes when app parameters evolve.
- **Feature 4**: The plugin translates DL Streamer Vision results from DL Streamer GStreamer Video
  Analytics (GVA) JSON format and pushes them back to Nx Witness as analytics objects (bounding
  boxes with labels), visible directly in the Nx Witness Desktop Client.

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
  DL Streamer Vision integrations.
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
