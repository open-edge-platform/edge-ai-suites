# How It Works

The application ingests RTSP streams, performs VLM inference, and delivers real-time alerts through a web dashboard.

![System Architecture](./_assets/Architecture.png)

## Data Flow

```text
RTSP Source → StreamManager (OpenCV/Circular Buffer)
            ↓
       AgentManager (Orchestrator) ↔ VLM Service (OpenAI-compatible API)
            ↓
       EventManager (SSE Pub/Sub) → Dashboard UI
```
