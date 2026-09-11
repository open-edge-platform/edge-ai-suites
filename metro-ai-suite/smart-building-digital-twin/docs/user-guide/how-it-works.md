# How It Works

The sample application provides:

- A seven-camera scene with looping RTSP video streams
- ATSS-MobileNetV2 detection model in INT8 (default for both GPU and CPU; override
  `MODEL_NAME` to `smartbuilding-fp16` if needed that uses YOLOX-S detection model)
- Badge and FaceID sensor replay synchronized to video loops via raw camera metadata
- Ambient-light sensor values change to reflect dark and live states as the camera
  video loops.
- Analytics dashboard at the configured `DASHBOARD_URL` with live scene narration
- Setup automation through `./setup.sh`

## High-Level Architecture

The sample application has the following architecture elements:

- Video and sensor sources
- Scenescape components for MediaMTX media router, Deep Learning Streamer (DL Streamer),
  scene controller, and MQTT broker
- An analytics container that runs narrator and dashboard services
- A browser dashboard that shows scene state, narrator feed, and event detail

```mermaid
flowchart BT
    subgraph src["Video &amp; Sensor Sources"]
        TS[".ts files<br/>looped video"]
        SJSON["sensors.json<br/>badge / FaceID / light"]
    end

    subgraph ss["Scenescape"]
        direction BT
        MTX["MediaMTX<br/>RTSP server"]
        DLS["DLStreamer<br/>YOLOX-S or ATSS-MobileNetV2 detection"]
        CTRL["scene controller<br/>track fusion"]
        BROKER["MQTT broker"]
        MTX --> DLS -->|detections| BROKER
        CTRL -->|tracked objects| BROKER
        BROKER --> CTRL
    end

    subgraph analytics["Analytics Container"]
        direction BT
        NAR["narrator.py<br/>event narration + alerts"]
        DASH["dashboard.py<br/>FastAPI"]
        NAR --> DASH
    end

    subgraph ui["Browser  DASHBOARD_URL"]
        STATE["Scene State<br/>live counts &amp; regions"]
        FEED["Narrator Feed<br/>events &amp; snapshots"]
        DETAIL["Event Detail<br/>expanded view"]
    end

    TS --> MTX
    SJSON -->|sensor_replay.py| BROKER
    BROKER -->|MQTT tracks| NAR
    DASH -->|SSE /stream/scene-state| STATE
    DASH -->|SSE /stream/narrator| FEED
    FEED --> DETAIL

    classDef source  fill:#2d4a6b,stroke:#4a7aab,color:#cce0ff
    classDef infra   fill:#3a3a5c,stroke:#6060a0,color:#d0d0ff
    classDef app     fill:#1e4d3a,stroke:#3a8a5a,color:#c0ffdc
    classDef browser fill:#4a3000,stroke:#c08000,color:#ffe0a0

    class TS,SJSON source
    class MTX,DLS,CTRL,BROKER infra
    class NAR,DASH app
    class STATE,FEED,DETAIL browser
```
