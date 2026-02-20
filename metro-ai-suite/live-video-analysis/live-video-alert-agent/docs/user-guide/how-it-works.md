## How It Works

The application ingests RTSP streams, performs VLM inference, and delivers real-time alerts through a web dashboard.

### Data Flow

```
RTSP Source → StreamManager (OpenCV/Circular Buffer)
            ↓
       AgentManager (Orchestrator) ↔ VLM Service (OpenAI-compatible API)
            ↓
       EventManager (SSE Pub/Sub) → Dashboard UI
```