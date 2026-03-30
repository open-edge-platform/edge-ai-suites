# Content Search

Content Search is a core multimodal service designed for smart classroom environments. It enables AI-driven video summarization, document text extraction, and semantic search capabilities using advanced RAG (Retrieval-Augmented Generation) workflows.

## Prerequisites
### 1. Core Services
| Component | Minimum Version | Description |
| :--- | :--- | :--- |
| **Python** | 3.12+ | Primary runtime for the backend orchestration framework. |
| **PostgreSQL** | 16+ | Relational database for task metadata and state management. |
| **MinIO** | Latest | Object storage for raw files (Videos, PDFs, Images). |
| **ChromaDB** | Latest | Vector database for embedding storage and semantic search. |

### 2. System Tools (Multimodal Processing)
To enable advanced document and video processing, the following must be installed and added to the system `PATH`:

* **Tesseract OCR**: Required for Optical Character Recognition (extracting text from images/PDFs).
* **Poppler**: Required for PDF rendering and frame extraction.

## Quick Start
### Automatic Dependency Installation
We provide a unified installation script that automates the setup of the databases, Python virtual environment, and core dependencies.

Note: Open PowerShell as Administrator before running the script.

```PowerShell
# Run the automation script from the content search root
./install.ps1
```
### Launching Services
Once the environment is configured, activate the virtual environment and start the orchestration service:

```PowerShell
# Navigate to the search module
cd content_search

# Activate the virtual environment
.\venv_content_search\Scripts\Activate.ps1

# Start all microservices
python start_services.py
```

## API Endpoints

| Endpoint | Method | Pattern | Description | Status |
| :--- | :---: | :---: | :--- | :---: |
| `/api/v1/system/health` | **GET** | SYNC | Backend app health check | DONE |
| `/api/v1/task/query/{task_id}` | **GET** | SYNC | Query status of a specific task | DONE |
| `/api/v1/task/list` | **GET** | SYNC | Query tasks by conditions (e.g., `?status=PROCESSING`) | DONE |
| `/api/v1/task/cancel/{task_id}` | **POST** | SYNC | Cancel a running task | WIP |
| `/api/v1/task/pause/{task_id}` | **POST** | SYNC | Pause a running task | WIP |
| `/api/v1/task/resume/{task_id}` | **POST** | SYNC | Resume a paused task | WIP |
| `/api/v1/object/files` | **GET** | SYNC | Query files in MinIO with filters | DONE |
| `/api/v1/object/upload` | **POST** | ASYNC | Upload a file to MinIO | DONE |
| `/api/v1/object/ingest` | **POST** | ASYNC | Ingest a specific file from MinIO | WIP |
| `/api/v1/object/ingest-text` | **POST** | ASYNC | Emedding a raw text | WIP |
| `/api/v1/object/upload-ingest` | **POST** | ASYNC | Upload to MinIO and trigger ingestion | DONE |
| `/api/v1/object/search` | **POST** | ASYNC | Search for files based on description | DONE |
| `/api/v1/object/download` | **POST** | STREAM | Download file from MinIO | DONE |
| `/api/v1/video/summarization` | **POST** | STREAM | Generate video summarization | WIP |

## API reference
[Content Search API reference](./docs/dev_guide/Content_search_API.md)

[Ingest and Retrieve](./docs/dev_guide/file_ingest_and_retrieve/API_GUIDE.md)

[Video Preprocess](./docs/dev_guide/video_preprocess/API_GUIDE.md)

[VLM OV Serving](./docs/dev_guide/vlm_openvino_serving/API_GUIDE.md)
