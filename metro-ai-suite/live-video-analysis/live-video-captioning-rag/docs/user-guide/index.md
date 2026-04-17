# Live Video Captioning RAG

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/live-video-analysis/live-video-captioning-rag">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/live-video-analysis/live-video-captioning-rag/README.md">
     Readme
  </a>
</div>
hide_directive-->

Live Video Captioning RAG sample application uses the Retrieval-Augmentation Generation technique, which transforms live video captions into a knowledge base. The sample application ingests captions from the Live Video Captioning sample application, generates semantic embeddings, and uses LLMs optimized through the OpenVINO™ toolkit to deliver AI-powered chatbot responses grounded in the video context. The sample application builds searchable caption embeddings and interacts with the video content through natural language queries.

<img src="./_assets/live-captioning-rag.gif" width="80%">

## Key Features

- **RAG-based Video Context**: Converts caption text from video frames into embeddings and store them in a vector database for semantic search and retrieval.

- **OpenVINO toolkit-LLM Integration**: Deploys large language models efficiently on Intel® hardware for context-aware response generation.

- **Interactive Chat Interface**: Web-based dashboard for querying video content with streaming responses and an inline preview of retrieved frames and captions.

- **Multi-Model Support**: Configurable embedding models and LLM models with flexible model switching for different use cases and performance requirements.

- **Multi-Device Support**: CPU and GPU device options for embedding generation and LLM inference, optimized for Intel® platforms.

- **REST API Endpoints**: Programmatic access to embedding ingestion (`/api/embeddings`) and chat queries (`/api/chat`) for integration with external systems.

- **Streaming Responses**: Real-time chat responses with full caption context and visual frame references for enhanced user understanding.

- **Deployment through Docker Compose tool**: Containerized stack for simplified setup and deployment across different environments.

## Use Cases

- **Video Content Search and Discovery**: Build searchable knowledge bases from surveillance, educational, or archival videos to find relevant scenes (or frames) and information quickly using natural language queries.

- **Real-time Video Analytics with Q&A**: Monitor live video feeds with the ability to ask questions about the video content and receive answers grounded in actual video captions and context.

- **Accessibility and Content Understanding**: Generate and query video captions to make the video content more accessible, and enable users to understand the video content without watching the full stream.

- **Intelligent Security and Safety**: Deploy RAG-backed chatbots for security monitoring workflows to answer questions about events, activities, and anomalies detected in surveillance video streams.

<!--hide_directive
:::{toctree}
:hidden:

./get-started.md
./how-it-works.md
./api-reference.md
./known-issues.md
Release Notes <./release-notes.md>

:::
hide_directive-->
