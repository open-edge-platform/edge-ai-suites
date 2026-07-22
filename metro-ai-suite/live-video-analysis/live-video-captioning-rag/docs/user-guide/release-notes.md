# Release Notes: Live Video Captioning RAG

<!--## Version 2026.2.0-->

<!--date TBD-->

## Version 2026.1.0

**June 17, 2026**

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

**New**

- The initial release with core RAG capabilities.
- Support for embedding and LLM models.
- Streaming response rendering.
- Inline frame preview with the caption context.
- Deployment with the Docker Compose tool for the stack.

**Known Issues**

- **Limited Standalone Functionality**: The sample application works with the
  [Live Video Captioning](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-suites/live-video-captioning/index.html)
  sample application. Running the sample application standalone provides limited context until embeddings are manually added.\
   _Workaround_: Use the provided demo script (`sample/demo_call_embedding.py`) to test the standalone functionality.
- **Platform Support**: The sample application is not validated either on the Standalone or Developer Node
  versions of Edge Microvisor Toolkit.

For detailed instructions, see [Get Started](./get-started.md).
