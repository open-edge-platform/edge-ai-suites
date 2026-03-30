# Content Search
## Prerequisites
1 python3
 python3.10

2 postgreSQL
postgreSQL installation refers to [PostgreSQL installation](./docs/dev_guide/Installation.md#postgresql)
3 Minio
minio installation refers to [Minio installation](./docs/dev_guide/Installation.md#minio)

4 System Tools: Required for multimodal processing:

- Tesseract OCR: For image/PDF text extraction.
- Poppler: For PDF rendering.

## Environment Setup
### Create/activate python venv
```powershell
# Create venv
& '<your python dir>' -m venv venv
.\venv\Scripts\Activate.ps1
```

###
```powershell
cd xxx/content_search
python -m pip install --upgrade pip
pip install -r .\requirements.txt
```
## Launch
```powershell
cd xxx/content_search
python .\start_services.py
```
// todo
## Avaliable Endpoints

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
