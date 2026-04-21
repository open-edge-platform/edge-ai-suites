# How It Works

The Live Video Captioning RAG sample application combines caption ingestion, vector search, and LLM-based response generation into a Retrieval-Augmented Generation workflow. The sample application works with the Live Video Captioning sample application that produces frame-level captions and metadata from an RTSP stream. Those captions become the knowledge base that the Live Video Captioning RAG sample application uses to answer questions.

![Architecture Diagram](./_assets/architecture.jpg "architecture diagram")

## Data Flow Diagram

```text
Live Video - → Live Video Captioning
                         |
                         ▼
User Query → Live Video Captioning RAG → Embedding Service → Vector Store -> Retrieve → Response
```

## System Components

### 1. Collection of Live Video Captioning application

[Live Video Captioning](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning/how-it-works.html) is the upstream producer in the full deployment flow. It analyzes the video stream, generates captions for frames, and sends frame data plus metadata to the RAG application so the RAG system can build searchable context.

The collection includes:

- **dlstreamer-pipeline-server**: Deep Learning Streamer Pipeline Server (DL Streamer Pipeline Server) that processes Real-Time Streaming Protocol (RTSP) sources with GStreamer pipelines and `gvagenai` for Vision-Language Model (VLM) inference.
- **mediamtx**: Web Real-Time Communication (WebRTC) and WebRTC-HTTP Ingestion Protocol (WHIP) signaling server for video streaming.
- **coturn**: Traversal Using Relays around NAT (TURN) server for NAT traversal in WebRTC connections.
- **video-caption-service**: Python backend that uses FastAPI, which serves REST APIs, Server-Sent Events (SSE) metadata streams, and WebSocket metrics.
- **collector**: Visual Pipeline and Platform Evaluation Tool that collects CPU, GPU, memory, and power system metrics.

### 2. Live Video Captioning RAG Sample Application

Live Video Captioning RAG Sample Application consists of a browser-based frontend and a FastAPI backend served by the same FastAPI application. The sample application provides:

- a chat interface for user questions
- streaming response rendering
- inline display of retrieved frame images and caption previews
- model information display

The backend in this component exposes the main APIs used by the UI and upstream pipelines:

- `POST /api/embeddings` to ingest caption-derived context
- `POST /api/chat` to answer questions with streaming output utilizing configured LLM runs through the OpenVINO™ backend.
- `GET /api/model` to report the active LLM model
- `GET /api/health` to report service health

### 3. Embedding Service

When new caption data arrives, the Live Video Captioning RAG backend sends the caption text to an embedding endpoint. The returned vector represents the semantic meaning of the caption text and is used for similarity search.

### 4. Visual Data Management System (VDMS) Vector Store

The sample application stores embeddings in a VDMS-backed vector database together with normalized metadata.
This allows the application to retrieve relevant text context and associated visual references during question answering.

## Deployment Note

This sample application is most effective when deployed together with the Live Video Captioning sample application. If you run the sample application only, the chat interface can still work, but the retrieved context will be limited until embeddings are added through the ingestion API or a demo workflow.

## Learn More

- [Get Started](./get-started.md)
- [System Requirements](./get-started/system-requirements.md)
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)
- [Release Notes](./release-notes.md)
