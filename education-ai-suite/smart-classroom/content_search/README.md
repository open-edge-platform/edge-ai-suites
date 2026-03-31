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
| `/api/v1/system/health` | **GET** | SYNC | **Backend Health Check**: Verifies the operational status of the backend services. |
| `/api/v1/task/query/{task_id}` | **GET** | SYNC | **Task Status Inspection**: Retrieves real-time metadata for a specific job, including current lifecycle state (PENDING, PROCESSING, COMPLETED, FAILED), and error logs if applicable. |
| `/api/v1/task/list` | **GET** | SYNC | **Batch Task Retrieval**: Queries task records. Supports filtering via query parameters (e.g., `?status=PROCESSING`) for monitoring system load and pipeline efficiency. |
| `/api/v1/object/upload` | **POST** | ASYNC | **File Persistence to MinIO**: Streams local binary data to the object store. Generates a unique Object Key based on run-scoped UUIDs and returns the URI for downstream pipeline referencing. |
| `/api/v1/object/ingest` | **POST** | ASYNC | **Pre-stored Asset Ingestion**: Triggers the AI pipeline for a file already existing in MinIO. Includes content extraction, chunking, and vector embedding. For video assets, it automatically executes a dedicated Video Summarization workflow. |
| `/api/v1/object/ingest-text` | **POST** | ASYNC | **Text-Specific Ingestion**: Specifically designed for text-based files (e.g., TXT, PDF) already stored in MinIO. Focuses on high-fidelity semantic segmentation and vector indexing for knowledge retrieval. |
| `/api/v1/object/upload-ingest` | **POST** | ASYNC | **Atomic Upload & Ingestion**: A unified workflow that first saves the file to MinIO and then immediately initiates the ingestion pipeline. Features full content indexing and **AI-driven Video Summarization** for supported video formats. |
| `/api/v1/object/search` | **POST** | ASYNC | **Semantic Content Retrieval**: Performs a similarity search across the vector store based on natural language descriptions. Returns matched content snippets and their corresponding MinIO file paths. |
| `/api/v1/object/download` | **POST** | STREAM | **File Download**: Fetches objects from MinIO using a streaming response. Optimized for large-scale multimedia (MP4, PDF) to maintain low memory overhead on the application server. |

## API reference
[Content Search API reference](./docs/dev_guide/Content_search_API.md)

[Ingest and Retrieve](./docs/dev_guide/file_ingest_and_retrieve/API_GUIDE.md)

[Video Preprocess](./docs/dev_guide/video_preprocess/API_GUIDE.md)

[VLM OV Serving](./docs/dev_guide/vlm_openvino_serving/API_GUIDE.md)
