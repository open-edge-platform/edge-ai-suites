# Release Notes: Live Video Captioning RAG Sample Application

## Version 1.0.0

**March, 2026**

The Live Video Captioning RAG sample application combines caption ingestion, vector search, and LLM-based response generation into a Retrieval-Augmented Generation workflow. The sample application processes text captioning generated from RTSP video streams through the Live Video Captioning application to deliver AI-powered chatbot responses based on text captioning context from video frames.

### Key Features
- **RAG-based Video Analysis**: Generates embeddings from video captions and store in vector database
- **OpenVINO LLM Integration**: Deploys LLM models efficiently using OpenVINO for response generation
- **Interactive Chatbot Interface**: Web-based dashboard for querying video content
- **Docker Compose Deployment**: Simplified deployment with containerized services
- **REST API**: Endpoints for embedding ingestion (`/api/embeddings`) and chat queries (`/api/chat`)
- **Multi-device Support**: CPU and GPU device options for embedding and LLM inference
- **Streaming Responses**: Real-time chat responses with retrieved frame references

### What's New
- Initial release with core RAG capabilities
- Support for embedding and LLM models
- Streaming response rendering
- Inline frame preview with caption context
- Deployment with the Docker Compose tool for the stack

### Known Issues
- **Limited Standalone Functionality**: The sample application works with the Live Video Captioning sample application. Running the sample application standalone provides limited context until embeddings are manually added.
- **Platform Support**: Intel does not validate the sample application on the EMT-S and EMT-D variants of the Edge Microvisor Toolkit.

### Configuration
- Device selection: CPU by default, or GPU
- Configurable LLM model and embedding model
- Environment setup via `scripts/setup_env.sh`

### Important Notes
- This release requires the Live Video Captioning sample application as the upstream data producer for a full functionality.
- Use the demo script provided (`sample/demo_call_embedding.py`) to test the standalone capability.
- Ensure containers reach the "healthy/running" state before accessing the application.

For detailed instructions, see [Get Started](./get-started.md).