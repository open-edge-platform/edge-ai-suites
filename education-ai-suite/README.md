# Education AI Suite

The **Education AI Suite** is a collection of education-focused AI applications, libraries, and benchmarking tools to help developers build intelligent classroom solutions faster. It provides audio and video pipelines accelerated with the OpenVINO™ toolkit, enabling high-performance deployment on **Intel® CPUs, integrated GPUs, and NPUs**.

This suite organizes workflows tailored for the education sector, with initial support for the **Smart Classroom** application—an extensible framework for processing, analyzing, and summarizing classroom sessions using advanced multimodal AI.

The main features are as follows:

**Audio Intelligence**:

- Audio transcription with ASR models (e.g., Whisper, Paraformer)
- Summarization using powerful LLMs (e.g., Qwen, LLaMA)
- Plug-and-play architecture for integrating new ASR and LLM models
- API-first design ready for frontend integration
- Extensible roadmap for real-time streaming, diarization, translation, and video analysis

**Video Intelligence**:

- Front Camera Pipeline: Student **pose detection**: sitting, standing, hand raise, leaning
- Rear Camera Pipeline: **Re-Identification (ReID)** to track students consistently across camera views
- Board Camera Pipeline: **Board content classification**

**Content Search & RAG**:

- **Retrieval Augmented Generation (RAG)**: Upload educational content (PDFs, documents, videos, images) and ask natural language questions
- **Multi-modal AI**: Combines vector search with LLM-powered question answering using OpenVINO
- **Multiple UI Options**: React-based web interface and Flutter cross-platform application(RAG)
- **Intelligent Q&A**: Context-aware question answering with cited sources
- **Content Management**: File upload, indexing, tagging, and management capabilities


### Flutter + RAG Integration

The Smart Classroom now includes a **Flutter application** (`utils/flutter/`) that provides a modern, cross-platform interface for the Content Search RAG pipeline. This integration demonstrates how educational applications can leverage local AI inference via OpenVINO for intelligent Retrieval Augmented Generation.

**Key Features**:
- Upload and ingest educational materials (documents, presentations, videos, images)
- Ask questions against indexed content with cited sources
- Multi-turn conversational Q&A with conversation history
- Tag-based content filtering
- File management (list, filter, delete indexed files)
- Cross-platform support (Windows desktop, Web)

**Two Ways to Use the Application**:

1. **Flutter UI** - Traditional graphical interface:
   - Run `.\utils\flutter\setup.ps1` to install dependencies
   - Run `.\utils\flutter\start.ps1` to launch the application
   - Interact via the Flutter desktop or web interface

2. **Coding Companion (Agentic Mode)** - AI-assisted workflow:
   - Use natural language commands in your coding assistant like GitHub Copilot, Claude, Cursor etc.,
   - Available skills automatically execute setup, upload files, ask questions, manage content
   - Example: `/sc-setup "first time set-up"`, `/sc-upload "upload a file"`, `/sc-qa "explain quantum computing"`

For detailed setup instructions, architecture overview, and coding companion usage, see [**Flutter + RAG Documentation**](utils/flutter/README.md).

## Full Documentation

For comprehensive setup, usage, and contribution guide, see
[**Smart Classroom Documentation**](smart-classroom/README.md).
