<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Smart Classroom Flutter + RAG Integration

A cross-platform Flutter application demonstrating **Retrieval Augmented Generation (RAG)** integration with the Smart Classroom Content Search backend. This application showcases how educational platforms can leverage **OpenVINO-accelerated AI** for intelligent content search, multi-turn Q&A, and document management.
---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Two Ways to Use This Application](#two-ways-to-use-this-application)
  - [Method 1: Traditional Flutter UI](#method-1-traditional-flutter-ui)
  - [Method 2: Coding Companion (Agentic Mode)](#method-2-coding-companion-agentic-mode)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Using the Coding Companion](#using-the-coding-companion)
- [Available Skills & Commands](#available-skills--commands)
- [Sample Prompts for Coding Companion](#sample-prompts-for-coding-companion)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Tech Stack](#tech-stack)

---

## Overview

The Smart Classroom Flutter application provides a modern, cross-platform interface for educational content management and AI-powered question answering. Built with **Flutter + Riverpod**, it communicates with the **Content Search backend** (powered by **FastAPI + OpenVINO**) to deliver:

- **Content Ingestion**: Upload PDFs, documents, presentations, images, and videos
- **Intelligent Q&A**: Ask natural language questions with RAG-powered responses and cited sources
- **Multi-turn Conversations**: Maintain conversation history for contextual follow-up questions
- **Content Management**: List, filter, and delete indexed files; manage tags
- **Local AI Inference**: All AI processing runs locally using OpenVINO on Intel hardware (CPU/NPU/iGPU)

This application demonstrates a **unique dual-interaction model**:
1. **Traditional UI**: Graphical Flutter interface for end users
2. **Agentic Mode**: AI coding companions that autonomously execute workflows via natural language commands

---

## Architecture

The Flutter app acts as a REST API client to the Content Search backend:

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Interaction Layer                       │
├─────────────────────────┬───────────────────────────────────────┤
│   Flutter UI            │   Coding Companion (Agentic Mode)     │
│   (Graphical Interface) │   (Natural Language Commands)         │
│                         │                                       │
│   • Upload Screen       │   Skills:                             │
│   • Q&A Screen          │   • sc-setup  - Setup environment     │
│   • Files Screen        │   • sc-up     - Start application     │
│                         │   • sc-upload - Upload & ingest       │
│                         │   • sc-qa     - Ask questions         │
│                         │   • sc-files  - Manage files          │
│                         │   • sc-doctor - Health diagnostics    │
└─────────────┬───────────┴───────────────┬───────────────────────┘
              │                           │
              └───────────┬───────────────┘
                          │
                          │ HTTP REST API
                          ▼
         ┌────────────────────────────────────────┐
         │      Content Search Backend            │
         │       (FastAPI +OpenVINO)              │
         ├────────────────────────────────────────┤
         │   • File upload & ingestion            │
         │   • Vector indexing                    │
         │   • LLM-powered Q&A                    │
         │   • Multi-modal processing             │
         │   • Task management                    │
         └─────────────┬──────────────────────────┘
                       │
                       ▼
         ┌────────────────────────────────────────┐
         │   OpenVINO Runtime                     │
         │   Intel Hardware Acceleration          │
         │   (CPU / NPU / iGPU)                   │
         └────────────────────────────────────────┘
```

**Key Components**:
- **Flutter Frontend**: Cross-platform UI (Windows Desktop, Web)
- **Content Search API**: REST endpoints for file management and RAG operations
- **OpenVINO Models**: Local inference for embeddings and LLM
- **Skill Files**: AI agent automation scripts in `.github/skills/`

---

## Features

### 🚀 Content Ingestion
- **Supported Formats**: PDF, TXT, DOCX, DOC, PPTX, PPT, XLSX, XLS, JPG, JPEG, PNG, MP4, AVI, MOV, MKV
- **Async Processing**: Background ingestion with task status polling
- **Duplicate Detection**: Automatic handling of duplicate files
- **Tag Management**: Organize content with custom tags

### 💬 Intelligent Q&A
- **RAG Pipeline**: Retrieval Augmented Generation for accurate, source-cited answers
- **Multi-turn Conversations**: Up to 3 conversation turns maintained for context
- **Tag Filtering**: Scope retrieval to specific content categories
- **Source Citations**: Every answer includes document name, type, and relevance score
- **Streaming Responses**: Real-time answer generation (backend support)

### 📁 File Management
- **List Files**: View all indexed files with metadata
- **Filter by Tags**: Show files matching specific tags
- **Delete Files**: Remove indexed content by file hash
- **View Tags**: List all available tags in the system

### 🤖 Agentic Companion
- **Natural Language Interface**: Control the application via coding assistants
- **Autonomous Execution**: Skills run commands directly, no manual intervention
- **Cross-Platform Agent Support**: Works with GitHub Copilot, Continue, Cursor, Claude Code, etc.
---

## Two Ways to Use This Application

### Method 1: Traditional Flutter UI

**For end users who prefer graphical interfaces:**

1. **Setup** (one-time):
   ```powershell
   .\utils\flutter\setup.ps1
   ```

2. **Launch**:
   ```powershell
   .\utils\flutter\start.ps1
   ```

3. **Interact**:
   - Open the Flutter desktop application or web interface
   - Navigate through screens: Upload, Q&A, Files
   - Upload content, ask questions, manage files

---

### Method 2: Coding Companion (Agentic Mode)

Instead of manually running commands or clicking through UI, **use natural language** to control the application through your coding assistant.

**How It Works**:
1. Open this workspace in VS Code
2. Start your coding companion (GitHub Copilot Chat, Continue, Cursor, etc.)
3. Type natural language commands
4. The agent reads the skill files (`.github/skills/`) and autonomously executes workflows

**Example Workflow**:
```
You: "Set up the Smart Classroom application"
Agent: [Reads sc-setup skill, runs setup.ps1, reports success]

You: "Start the application"
Agent: [Reads sc-up skill, runs start.ps1, verifies health endpoint]

You: "Upload the PDF"
Agent: [Reads sc-upload skill, uploads file, polls task until COMPLETED]

You: "Ask a question: What is quantum computing?"
Agent: [Reads sc-qa skill, calls Q&A API, returns answer with sources]

You: "List all indexed files"
Agent: [Reads sc-files skill, calls files endpoint, displays table]
```

---

## Prerequisites

### System Requirements
- **Operating System**: Windows 10/11 (primary)
- **Flutter SDK**: 3.22+ / Dart 3.3+
- **Python**: 3.12
- **Hardware**: Intel CPU (NPU/iGPU recommended for best performance)

### Software Dependencies
- **PowerShell 7+** (for automation scripts)
- **VS Code** (recommended for agentic mode)
- **Coding Companion** (optional): GitHub Copilot, Continue, Cursor, Claude Code, etc.

### Network
- **Internet access** for first-time model downloads
---

## Quick Start

### Traditional UI Mode

```powershell
# 1. Clone the repository (if not already done)
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/education-ai-suite

# 2. Run setup (one-time)
.\utils\flutter\setup.ps1

# 3. Start the application
.\utils\flutter\start.ps1

# 4. Open browser or desktop app
# Backend: http://127.0.0.1:9011
# Flutter Web: http://localhost:5000 (or desktop window)
```

### Agentic Mode (Coding Companion)

```powershell
# 1. Open workspace in VS Code
code .

# 2. Open Copilot Chat / Continue / Cursor

# 3. Type any of these commands:
"set up smart classroom"
"start smart classroom"
"check if the backend is healthy"
"upload sample-files/document.pdf"
"ask a question: Explain the main concepts"
"list all indexed files"
```

The agent will read the appropriate skill file and execute the workflow automatically.

---

## Using the Coding Companion

### What Are Skills?

**Skills** are structured Markdown files (`.github/skills/*/SKILL.md`) that teach AI coding assistants how to automate specific workflows. Each skill contains:
- **YAML Frontmatter**: Name, description, trigger phrases
- **Workflow Instructions**: Step-by-step PowerShell commands
- **Troubleshooting Guide**: Common errors and fixes

When you type a trigger phrase (e.g., "upload a file"), the agent:
1. Searches for the matching skill
2. Reads the skill's instructions
3. Executes commands directly in your terminal
4. Reports results back to you

**No manual copy-paste required!** The agent does all the work.

---

### Supported Coding Companions

This application works with any AI coding assistant that can:
- Read Markdown skill files
- Execute terminal commands
- Parse JSON/YAML frontmatter

---

## Available Skills & Commands

All skills are located in `.github/skills/`. Here's what each skill does:

| Skill | Purpose | Trigger Phrases | What It Does |
|-------|---------|-----------------|--------------|
| **sc-setup** | One-time environment setup | "set up smart classroom", "run setup", "first time setup", "install dependencies" | • Verifies Flutter SDK<br>• Runs `flutter pub get`<br>• Creates Python venv<br>• Installs backend requirements |
| **sc-up** | Start application | "start smart classroom", "run the app", "launch smart classroom", "bring up services" | • Runs `start.ps1` script<br>• Starts backend on port 9011<br>• Launches Flutter app<br>• Verifies health endpoint |
| **sc-doctor** | Health diagnostics | "is the backend up", "check health", "backend unreachable", "debug backend" | • Probes `/api/v1/system/health`<br>• Diagnoses connectivity issues<br>• Checks Python venv<br>• Reviews logs |
| **sc-upload** | Upload & ingest files | "upload a file", "ingest a document", "upload pdf", "index a file", "add course material" | • Uploads file via multipart POST<br>• Polls task until COMPLETED<br>• Handles duplicates (cleanup-retry)<br>• Reports success/failure |
| **sc-qa** | Ask questions (RAG) | "ask a question", "query the content", "what does the document say", "RAG question", "multi-turn Q&A" | • Sends question to `/api/v1/object/qa`<br>• Includes conversation history<br>• Supports tag filtering<br>• Returns answer + sources |
| **sc-files** | Manage indexed files | "list files", "show indexed files", "delete a file", "remove file", "list tags", "manage files" | • Lists all files with metadata<br>• Shows available tags<br>• Deletes files by hash<br>• Filters by tags |

---

## Sample Prompts for Coding Companion

Copy-paste these into your AI coding assistant to see agentic mode in action:

### 🔧 Setup & Launch
```
Set up the Smart Classroom application for the first time.
```

```
Start the Smart Classroom application and verify the backend is healthy.
```

### 📤 Upload Content
```
Upload the file at "C:\Users\...\Documents\my-course-notes.pdf" to the Content Search backend.
```

```
Upload all PDF files in the sample-files directory.
```

### 💬 Ask Questions
```
Ask a question against the indexed content: "What are the key concepts covered in the course?"
```

```
Ask a follow-up question: "Can you explain the second concept in more detail?" (maintains conversation history)
```

```
Ask a question filtered by the tag "physics": "What is quantum entanglement?"
```

### 📁 File Management
```
List all files currently indexed in the Content Search backend.
```

```
List all available tags in the system.
```

```
Delete the file with hash abc123def456 from the indexed content.
```

### 🩺 Diagnostics
```
Check if the Content Search backend is healthy and running.
```

```
Debug why the Flutter app can't connect to the backend.
```

### 🚀 Full Workflow
```
I want to test the Smart Classroom RAG pipeline:
1. Set up the environment
2. Start the application
3. Upload sample-files/quantum-physics.pdf
4. Ask the question: "What is quantum computing?"
5. List all indexed files
```

The agent will execute all 5 steps autonomously!

---

## API Endpoints

The Content Search backend exposes the following REST API (base URL: `http://127.0.0.1:9011`):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/system/health` | Health check (returns `{"status":"ok"}`) |
| `POST` | `/api/v1/object/upload-ingest` | Upload file + start ingestion (multipart/form-data) |
| `GET` | `/api/v1/task/query/{task_id}` | Check ingestion task status |
| `DELETE` | `/api/v1/object/cleanup-task/{task_id}` | Cleanup failed/duplicate task |
| `POST` | `/api/v1/object/qa` | Ask question (RAG Q&A) |
| `GET` | `/api/v1/object/tags` | List all tags |
| `GET` | `/api/v1/object/files/list` | List indexed files |
| `DELETE` | `/api/v1/object/files/{file_hash}` | Delete file by hash |


For detailed request/response schemas, see `.github/skills/*/references/`.

---

## Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| `flutter: command not found` | Flutter not in PATH | Install Flutter SDK and add to PATH |
| `Connection refused on port 9011` | Backend not running | Run `.\utils\flutter\start.ps1` or `sc-up` skill |
| `Task status: FAILED` | Model download failed / Disk space | Check `smart-classroom/content_search/logs/` for errors |
| `401 Unauthorized` | (Future) Auth not configured | This app doesn't use auth yet |
| `Duplicate file (code 40901)` | File already indexed | Use sc-upload skill (auto-handles cleanup-retry) |
| Agent doesn't respond | Skill file not found | Ensure `.github/skills/` exists and skill frontmatter is valid |
| Proxy errors | Corporate firewall | Set `$env:HTTPS_PROXY = "http://proxy:port"` |

### Debugging Backend

```powershell
# Check if backend process is running
Get-Process | Where-Object {$_.Name -like "*python*"}

# View backend logs
Get-Content smart-classroom\content_search\logs\app.log -Tail 50

# Test health endpoint manually
Invoke-WebRequest -Uri "http://127.0.0.1:9011/api/v1/system/health" -UseBasicParsing
```

### Debugging Flutter

```powershell
# Check Flutter environment
flutter doctor -v

# Run Flutter in verbose mode
flutter run -d windows --verbose

# Clear Flutter build cache
flutter clean
flutter pub get
```

### Debugging Agentic Mode

If your coding companion doesn't recognize skills:
1. **Verify skill files exist**: `.github/skills/*/SKILL.md`
2. **Check YAML frontmatter syntax** (must be valid YAML)
3. **Use exact trigger phrases** from skill descriptions
4. **Ensure agent has file read permissions** in workspace
5. **Try rephrasing**: "Use the sc-upload skill to upload a PDF"

---

## Tech Stack

### Frontend (Flutter)
- **Flutter 3.22+** - Cross-platform UI framework
- **Dart 3.3+** - Programming language
- **Riverpod 2.x** - State management
- **Dio 5.x** - HTTP client
- **File Picker** - File selection dialogs
- **Path Provider** - File system access

### Backend (Content Search)
- **FastAPI** - Python web framework
- **LangChain** - LLM orchestration
- **OpenVINO** - AI inference runtime
- **FAISS** - Vector similarity search
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

### AI Models (OpenVINO)
- **Embeddings**: BGE, all-MiniLM, Sentence Transformers
- **LLM**: Qwen, LLaMA, Mistral (quantized INT4/INT8)
- **Multimodal**: Vision-Language Models (VLM) for image understanding

### Infrastructure
- **PowerShell 7+** - Automation scripts
- **Python 3.12** - Backend runtime
- **Git** - Version control
- **VS Code** - Recommended IDE

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

### Adding New Skills

To create a new skill:
1. Create folder: `.github/skills/my-skill/`
2. Add `SKILL.md` with YAML frontmatter:
   ```yaml
   ---
   name: my-skill
   description: What this skill does
   license: Apache-2.0
   metadata:
     version: "1.0.0"
     tags: "sc operational custom"
   ---
   ```
3. Write workflow instructions (PowerShell commands)
4. Update `.github/skills/skill-catalog.json`
5. Test with coding companion

---

## Related Documentation

- [Main Education AI Suite README](../../README.md)
- [Smart Classroom Backend Documentation](../../smart-classroom/README.md)
- [Content Search API Documentation](../../smart-classroom/content_search/README.md)
- [Skills Catalog](../../.github/skills/README.md)
- [Copilot Instructions](../../.github/copilot-instructions.md)

---

Demonstrating the power of **OpenVINO + Flutter + Agentic AI** for education.
