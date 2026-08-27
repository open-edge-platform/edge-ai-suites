# Release Notes: Live Video Captioning RAG

## Version 2026.2.0

**Release Date**: September 9, 2026

**New**:

- Decoupled RAG-related charts, Docker Compose assets, and documentation from the Live Video Captioning folder into an independent Live Video Captioning RAG structure.
- Integrated dedicated charts and Docker Compose configuration for Live Video Captioning RAG, designed to work together with the existing Live Video Captioning application.
- Updated documentation to reflect the decoupled architecture, dedicated deployment assets, and all related workflow changes.
- Bumped dependency package versions to address reported vulnerabilities.

**Known Issues**:

- The sample application is not validated either on the Standalone or Developer Node
  versions of Edge Microvisor Toolkit.

## Version 2026.1.0

**June 17, 2026**:

The Live Video Captioning RAG sample application combines caption ingestion, vector search,
and LLM-based response generation into a Retrieval-Augmented Generation workflow. The sample
application processes text captions generated from RTSP video streams through the Live Video
Captioning application to deliver AI-powered chatbot responses based on text captioning
context from video frames. The application leverages the following key features:

- **RAG-based Video Analysis**: Generates embeddings from video captions and stores them in a vector database.
- **OpenVINO LLM Integration**: Deploys LLM models efficiently using OpenVINO for response generation.
- **Interactive Chatbot Interface**: A web-based dashboard for querying video content.
- **Docker Compose Deployment**: Simplified deployment with containerized services.
- **REST API**: Endpoints for embedding ingestion (`/api/embeddings`) and chat queries (`/api/chat`).
- **Multi-device Support**: CPU and GPU device options for embedding and LLM inference.
- **Streaming Responses**: Real-time chat responses with the retrieved frame references.

**New**:

- The initial release with core RAG capabilities.
- Support for embedding and LLM models.
- Streaming response rendering.
- Inline frame preview with the caption context.
- Deployment with the Docker Compose tool for the stack.

**Known Issues**:

- **Limited Standalone Functionality**: The sample application works with the
  [Live Video Captioning](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-suites/live-video-captioning/index.html)
  sample application. Running the sample application standalone provides limited context until embeddings are manually added.\
   _Workaround_: Use the provided demo script (`sample/demo_call_embedding.py`) to test the standalone functionality.
- **Platform Support**: The sample application is not validated either on the Standalone or Developer Node
  versions of Edge Microvisor Toolkit.

For detailed instructions, see [Get Started](./get-started.md).
