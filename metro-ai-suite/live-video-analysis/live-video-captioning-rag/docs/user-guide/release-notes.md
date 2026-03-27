# Release Notes: Live Video Captioning RAG

## Version 1.0.0

**March, 2026**

The Live Video Captioning RAG sample application combines caption ingestion, vector search, and LLM-based response generation into a Retrieval-Augmented Generation workflow. It processes text captioning generated from RTSP video streams through the Live Video Captioning application to deliver AI-powered chatbot responses based on text captioning context from video frames.

### Key Features
- **RAG-based Video Analysis**: Generate embeddings from video captions and store in vector database
- **OpenVINO LLM Integration**: Deploy LLM models efficiently using OpenVINO for response generation
- **Interactive Chatbot Interface**: Web-based dashboard for querying video content
- **Docker Compose Deployment**: Simplified deployment with containerized services
- **REST API**: Endpoints for embedding ingestion (`/api/embeddings`) and chat queries (`/api/chat`)
- **Multi-device Support**: CPU and GPU device options for embedding and LLM inference
- **Streaming Responses**: Real-time chat responses with retrieved frame references

### What's New
- Initial release with core RAG capabilities
- Support for embedding and llm models
- Streaming response rendering
- Inline frame preview with caption context
- Docker Compose deployment for the stack

### Known Issues
- **Limited Standalone Functionality**: Application is designed to work with Live Video Captioning. Running standalone provides limited context until embeddings are manually added
- **Platform Support**: Not validated on EMT-S and EMT-D platforms

### Configuration
- Device selection: CPU (default) or GPU
- Configurable LLM model and embedding model
- Environment setup via `scripts/setup_env.sh`

### Important Notes
- This release requires Live Video Captioning as the upstream data producer for full functionality
- Use the provided demo script (`sample/demo_call_embedding.py`) to test standalone capability
- Ensure containers reach "healthy/running" state before accessing the application

For detailed instructions, see [Get Started](./get-started.md).