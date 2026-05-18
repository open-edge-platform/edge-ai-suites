# Content Search

Content Search is a multimodal service for smart classroom environments. It enables AI-driven video summarization, document text extraction, and semantic search capabilities.

## Features

- **Multimodal Semantic Search** — text and image queries across videos, documents, and images using CLIP and BGE embeddings
- **Video Summarization** — VLM-powered chunk-by-chunk summarization enabling text-based video retrieval
- **Document Ingestion** — full-text extraction with OCR support, semantic chunking, and vector indexing
- **RAG Q&A** — retrieval-augmented generation for answering questions over uploaded materials
- **File Management** — upload, index, search, download, and delete with full lifecycle tracking

## Quick Start

For installation and setup instructions, see [Get Started](../docs/user-guide/get-started.md#step-4-set-up-content-search).

## API Endpoints

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/v1/task/query/{task_id}` | GET | Task status inspection |
| `/api/v1/task/list` | GET | Batch task retrieval with filtering |
| `/api/v1/object/files/list` | GET | Indexed files inventory |
| `/api/v1/object/files/{file_hash}` | DELETE | Direct file deletion |
| `/api/v1/object/ingest-text` | POST | Text ingestion for semantic indexing |
| `/api/v1/object/upload-ingest` | POST | Unified upload and ingestion |
| `/api/v1/object/search` | POST | Semantic search (text or image query) |
| `/api/v1/object/qa` | POST | RAG-based question & answer |
| `/api/v1/object/download` | GET | File download/preview |
| `/api/v1/object/tags` | GET | List all tags |
| `/api/v1/object/cleanup-task/{task_id}` | DELETE | Task and resource cleanup |
| `/api/v1/system/config` | GET | System configuration |
| `/api/v1/system/reconcile` | POST | Storage consistency check |

## Documentation

- **User Guide**: [Get Started](../docs/user-guide/get-started.md#step-4-set-up-content-search-optional)
- **Dev Guide**: [Content Search API Reference](../docs/dev-guide/content-search/Content_search_API.md)
- **Microservice APIs**:
  - [File Ingest & Retrieve](../docs/dev-guide/content-search/file_ingest_and_retrieve/API_GUIDE.md)
  - [Video Preprocess](../docs/dev-guide/content-search/video_preprocess/API_GUIDE.md)
  - [VLM OpenVINO Serving](../docs/dev-guide/content-search/vlm_openvino_serving/API_GUIDE.md)
- **Design Docs**:
  - [Document Parser](../docs/dev-guide/content-search/file_ingest_and_retrieve/document_parser.md)
  - [Reranker / PostProcessor](../docs/dev-guide/content-search/file_ingest_and_retrieve/reranker.md)
