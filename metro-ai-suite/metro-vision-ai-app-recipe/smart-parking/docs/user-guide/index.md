# Smart Parking

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking/README.md">
     Readme
  </a>
  <a class="icon_download" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking/docs/user-guide/get-started.md">
     Installation guide
  </a>
</div>
hide_directive-->

The Smart Parking application optimizes parking management with AI-driven video analytics. It identifies and counts available parking spaces in real-time, accurately detecting empty slots. By monitoring parking areas, it tracks occupancy changes and provides current parking availability information.

The solution records occupied parking spaces, enabling efficient use and reporting. It enhances parking efficiency and improves user experience by offering real-time insights into parking operations.

Using advanced technologies and pre-trained deep learning models, the application processes and analyzes video streams in real-time. Its modular architecture and integration capabilities allow users to customize and extend functionalities to meet specific needs.

## How It Works

The architecture is designed to facilitate seamless integration and operation of various components involved in AI-driven video analytics.

![Architecture Diagram](./_assets/smart-parking-architecture.drawio.svg)

### Components

- **DL Streamer Pipeline Server (VA Pipeline):** Processes video frames, extracts metadata, and integrates AI inference results.
- **Mosquitto MQTT Broker:** Facilitates message communication between components like Node-RED and DL Streamer Pipeline Server using the MQTT protocol.
- **Node-RED:** A low-code platform for setting up application-specific rules and triggering MQTT-based events.
- **WebRTC Stream Viewer:** Displays real-time video streams processed by the pipeline for end-user visualization.
- **Grafana Dashboard:** A monitoring and visualization tool for analyzing pipeline metrics, logs, and other performance data.
- **Inputs (Video Files and Cameras):** Provide raw video streams or files as input data for processing in the pipeline.
- **Nginx:** High-performance web server and reverse proxy that provides TLS termination and unified HTTPS access.

The DL Streamer Pipeline Server is a core component, designed to handle video analytics at the edge. It leverages pre-trained deep learning models to perform tasks such as object detection, classification, and tracking in real-time. The DL Streamer Pipeline Server is highly configurable, allowing users to adjust parameters like detection thresholds and object types to suit specific use cases. This flexibility ensures that users can deploy AI-driven video analytics solutions quickly and efficiently, without the need for extensive coding or deep learning expertise.

It integrates various components such as MQTT, Node-RED, and Grafana to provide a robust and flexible solution for real-time video inference pipelines. The tool is built to be user-friendly, allowing customization without the need for extensive coding knowledge. Validate your ideas by developing an end-to-end solution faster.

## Learn More
- [System Requirements](./get-started/system-requirements.md)
- [Get Started](./get-started.md)
- [How to customize application](./how-to-customize-application.md)
- [DL Streamer Pipeline Server](./https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/index.html)
- [Release Notes](./release-notes.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-to-customize-application
how-to-generate-offline-package
how-to-use-gpu-for-inference
how-to-view-telemetry-data
how-to-benchmark
troubleshooting
release-notes

:::
hide_directive-->
