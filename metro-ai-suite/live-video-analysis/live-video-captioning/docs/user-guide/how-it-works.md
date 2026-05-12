# How it Works

The stack ingests an RTSP stream, runs a DLStreamer pipeline that samples frames for VLM inference, and sends results to the dashboard.

![System Architecture Diagram](./_assets/architecture.jpg "system architecture")

## Data Flow

```mermaid
flowchart LR
  subgraph FLOW["Data Flow"]
    RTSP["RTSP Source"] --> DPS["DL Streamer Pipeline Server"]
    DPS -->|"1fps AI branch\n(GStreamer gvagenai)"| MQTT["MQTT Broker"]
    DPS -->|"30fps preview"| MTX["mediamtx (WebRTC)"]
    MTX --> DASH["Dashboard"]
    DASH --> METRICS["Dashboard collects metrics\n(CPU, GPU, RAM)"]
  end
```

## System Components

- **dlstreamer-pipeline-server**: Intel DLStreamer Pipeline Server processing RTSP sources with GStreamer pipelines and `gvagenai` for VLM inference
- **mediamtx**: WebRTC/WHIP signaling server for video streaming
- **coturn**: TURN server for NAT traversal in WebRTC connections
- **app**: Python FastAPI backend serving REST APIs, SSE metadata streams, and WebSocket metrics
- **collector**: Intel VIP-PET system metrics collector (CPU, GPU, memory, power)

## Learn More

- [System Requirements](./get-started/system-requirements.md)
- [Get Started](./get-started.md)
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)
- [Release Notes](./release-notes.md)
