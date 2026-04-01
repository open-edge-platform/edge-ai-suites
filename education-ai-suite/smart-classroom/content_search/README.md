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

| Endpoint | Method | Pattern | Description |
| :--- | :---: | :---: | :--- |
| `/api/v1/task/query/{task_id}` | **GET** | SYNC | **Task Status Inspection**: Retrieves real-time metadata for a specific job, including current lifecycle state (e.g. PROCESSING, COMPLETED, FAILED), and error logs if applicable. |
| `/api/v1/task/list` | **GET** | SYNC | **Batch Task Retrieval**: Queries task records. Supports filtering via query parameters (e.g., `?status=PROCESSING`) for monitoring system load and pipeline efficiency. |
| `/api/v1/object/ingest-text` | **POST** | ASYNC | **Text-Specific Ingestion**: Primarily processes raw text strings passed in the request body for semantic indexing. It also supports fetching content from existing text-based objects in MinIO. |
| `/api/v1/object/upload-ingest` | **POST** | ASYNC | **Atomic Upload & Ingestion**: A unified workflow that first saves the file to MinIO and then immediately initiates the ingestion pipeline. Features full content indexing and AI-driven Video Summarization for supported video formats. |
| `/api/v1/object/search` | **POST** | SYNC | **Semantic Content Retrieval**: Executes a similarity search across vector collections using either natural language queries or base64-encoded images. Returns ranked results with associated metadata and MinIO object references. |
| `/api/v1/object/download` | **POST** | STREAM | **Original File Download**: Securely fetches the raw source file directly from MinIO storage. Utilizes stream-bridging to pipe binary data to the client. |

For detailed descriptions and examples of each endpoint, please refer to the: [Content Search API reference](./docs/dev_guide/Content_search_API.md)

## Components API reference
[Ingest and Retrieve](./docs/dev_guide/file_ingest_and_retrieve/API_GUIDE.md)

[Video Preprocess](./docs/dev_guide/video_preprocess/API_GUIDE.md)

[VLM OV Serving](./docs/dev_guide/vlm_openvino_serving/API_GUIDE.md)
