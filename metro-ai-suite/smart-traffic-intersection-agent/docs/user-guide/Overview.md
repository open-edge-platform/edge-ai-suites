# Smart Traffic Intersection Agent

The Smart Traffic Intersection Agent is a comprehensive traffic analysis service that provides real-time intersection monitoring, directional traffic density analysis, and Vision Language Model (VLM) powered traffic insights. It processes MQTT traffic data, manages camera images, and delivers intelligent traffic analysis through RESTful APIs.

## Overview

The microservice processes real-time traffic data from MQTT streams and provides advanced analytics including directional traffic density monitoring, VLM-powered traffic scene analysis, and comprehensive traffic summaries. It supports sliding window analysis, sustained traffic detection, and intelligent camera image management for enhanced traffic insights.

## How It Works

The diagram below illustrates the high-level architecture of the Smart Traffic Intelligence Agent, showcasing its core components and their interactions with external systems.

<p align="center">
    <img src="./_images/ITT_architecture.png" alt="Architecture" />
</p>

The Smart Traffic UI below shows how traffic, weather data is analyzed and summary, alerts are shown to the user.

<p align="center">
    <img src="./_images/traffic_agent_ui.png" alt="Traffic Intersection Agent UI" />
</p>

## Components

The Smart Traffic Intelligence stack includes these containerized services:

- **MQTT Broker** (Eclipse Mosquitto) - Message broker for traffic data
- **DL Streamer Pipeline Server** - Video analytics and AI inference
- **SceneScape Database** - Configuration and metadata storage
- **SceneScape Web Server** - Management interface
- **SceneScape Controller** - Orchestration service
- **VLM OpenVINO Serving** - Vision Language Model inference
- **Traffic Intelligence** - Real-time traffic analysis with dual interface (API + UI)

### Key Integration Points

- **MQTT Communication**: All services communicate via the shared MQTT broker
- **Docker Network**: Services discover each other via Docker service names
- **Shared Secrets**: TLS certificates and auth files mounted from `src/secrets/`
- **Persistent Storage**: Traffic data stored in Docker volume `traffic-intelligence-data`
- **Health Monitoring**: All services include health check endpoints


## Supporting Resources

- [Get Started Guide](get-started.md)
- [API Reference](api-reference.md)
- [System Requirements](system-requirements.md)
