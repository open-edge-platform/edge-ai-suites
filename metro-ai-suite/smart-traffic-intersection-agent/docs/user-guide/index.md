# Smart Traffic Intersection Agent

<!--hide_directive
::::{container} component_header_row
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/smart-traffic-intersection-agent">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-traffic-intersection-agent/README.md">
     Readme
  </a>
</div>
hide_directive-->

> Note:
> This is a sample application **intended for evaluation and development purposes only**.
  For more information, refer to
  [Intended Use](https://docs.openedgeplatform.intel.com/dev/OEP-articles/notes-on-usage.html#intended-use)

<!--hide_directive :::: hide_directive-->


The Smart Traffic Intersection Agent demonstrates how Intel hardware performs in AI solutions
for urban traffic management. It presents the use case of a comprehensive traffic analysis
service that provides real-time intersection monitoring, analyzes directional traffic density,
and provides traffic insights powered by a Vision Language Model (VLM).

The agent processes MQTT traffic data, manages camera images, and delivers intelligent traffic
analysis through RESTful APIs. It supports sliding-window analysis, sustained traffic detection,
and intelligent management of camera images to enhance traffic insights.

Here is its high-level architecture diagram, showcasing its core components and their
interactions with external systems:

![ITT architecture](./_assets/ITT_architecture.png)

The Smart Traffic UI below shows how traffic and weather data is analyzed, and how summary
and alerts are shown to the user:

![traffic intersection agent UI](./_assets/traffic_agent_ui.png)

## Components

The Smart Traffic Intersection stack includes the following containerized services:

- **MQTT Broker** (Eclipse Mosquitto message broker) - Message broker for traffic data
- **DL Streamer Pipeline Server** - Video analytics and AI inference
- **Scenescape Database** - Configuration and metadata storage
- **Scenescape Web Server** - Management interface
- **Scenescape Controller** - Orchestration service
- **VLM OpenVINO Serving** - Vision Language Model inference
- **Traffic Intelligence** - Real-time traffic analysis with dual interface (API and UI)

### Key Integration Points

- **MQTT Communication**: All services communicate via the shared MQTT broker
- **Docker Network**: Services discover each other via Docker service names
- **Shared Secrets**: TLS certificates and auth files mounted from `src/secrets/`
- **Persistent Storage**: Traffic data stored in Docker volume `traffic-intelligence-data`
- **Health Monitoring**: All services include health check endpoints

## Learn More

- [Get Started Guide](./get-started.md)
- [API Reference](./api-reference.md)
- [System Requirements](./get-started/system-requirements.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
api-reference
Release Notes <release-notes>

:::
hide_directive-->
