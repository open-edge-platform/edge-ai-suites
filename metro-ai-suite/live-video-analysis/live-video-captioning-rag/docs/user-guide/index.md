# Live Video Captioning RAG User Guide

Live Video Captioning RAG is a Retrieval-Augmented Generation application that transforms live video captions into an knowledge base. It ingests captions from the Live Video Captioning sample application, generates semantic embeddings, and uses OpenVINO™ LLMs to deliver AI-powered chatbot responses grounded in video context. It build searchable caption embeddings, and interact with video content through natural language queries.

## Key Features

**RAG-based Video Context**: Convert caption text from video frames into embeddings and store them in a vector database for semantic search and retrieval.

**OpenVINO LLM Integration**: Deploy large language models efficiently on Intel hardware for context-aware response generation.

**Interactive Chat Interface**: Web-based dashboard for querying video content with streaming responses and inline preview of retrieved frames and captions.

**Multi-Model Support**: Configurable embedding models and LLM models with flexible model switching for different use cases and performance requirements.

**Multi-Device Support**: CPU and GPU device options for both embedding generation and LLM inference, optimized for Intel platforms.

**REST API Endpoints**: Programmatic access to embedding ingestion (`/api/embeddings`) and chat queries (`/api/chat`) for integration with external systems.

**Streaming Responses**: Real-time chat responses with full caption context and visual frame references for enhanced user understanding.

**Docker Compose Deployment**: Containerized stack for simplified setup and deployment across different environments.

## Use Cases

**Video Content Search and Discovery**: Build searchable knowledge bases from surveillance, educational, or archival videos to quickly find relevant scenes/frames and information using natural language queries.

**Real-time Video Analytics with Q&A**: Monitor live video feeds with the ability to ask questions about video content and receive answers grounded in actual video captions and context.

**Accessibility and Content Understanding**: Generate and query video captions to make video content more accessible and enable users to understand video content without watching the full stream.

**Intelligent Security and Safety**: Deploy RAG-backed chatbots for security monitoring workflows to answer questions about events, activities, and anomalies detected in surveillance video streams.