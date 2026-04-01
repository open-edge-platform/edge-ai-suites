# Content Search

Content Search is a core multimodal service designed for smart classroom environments. It enables AI-driven video summarization, document text extraction, and semantic search capabilities using advanced RAG (Retrieval-Augmented Generation) workflows.

## Quick Start
### Automatic Dependency Installation
We provide a unified installation script that automates the setup of the databases, Python virtual environment, and core dependencies.

Note: Open PowerShell as Administrator before running the script.

```PowerShell
# Run the automation script from the content search root
.\install.ps1
```
### Launching Services
Once the environment is configured, activate the virtual environment and start the orchestration service:

```PowerShell
# Activate the virtual environment
.\venv_content_search\Scripts\Activate.ps1

# Start all microservices
python .\start_services.py
```

## API Endpoints

| Endpoint | Method | Pattern | Description | Status |
| :--- | :---: | :---: | :--- | :---: |
| `/api/v1/system/health` | **GET** | SYNC | Backend app health check | DONE |
| `/api/v1/task/query/{task_id}` | **GET** | SYNC | Query status of a specific task | DONE |
| `/api/v1/task/list` | **GET** | SYNC | Query tasks by conditions (e.g., `?status=PROCESSING`) | DONE |
| `/api/v1/object/upload` | **POST** | ASYNC | Upload a file to MinIO | DONE |
| `/api/v1/object/ingest` | **POST** | ASYNC | Ingest a specific file from MinIO | DONE |
| `/api/v1/object/ingest-text` | **POST** | ASYNC | Emedding a raw text | DONE |
| `/api/v1/object/upload-ingest` | **POST** | ASYNC | Upload to MinIO and trigger ingestion | DONE |
| `/api/v1/object/search` | **POST** | ASYNC | Search for files based on description | DONE |
| `/api/v1/object/download` | **POST** | STREAM | Download file from MinIO | DONE |

## API reference
[Content Search API reference](./docs/dev_guide/Content_search_API.md)

[Ingest and Retrieve](./docs/dev_guide/file_ingest_and_retrieve/API_GUIDE.md)

[Video Preprocess](./docs/dev_guide/video_preprocess/API_GUIDE.md)

[VLM OV Serving](./docs/dev_guide/vlm_openvino_serving/API_GUIDE.md)
