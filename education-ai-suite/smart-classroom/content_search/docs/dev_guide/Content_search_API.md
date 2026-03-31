# API Reference Guide - Content search

This document defines the communication protocol between the Frontend and Backend for asynchronous file processing tasks.

---

## Global Response Specification

All HTTP Response bodies must follow this unified JSON structure:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| **code** | Integer | Yes | Application Logic Code. 20000 indicates success; others are logical exceptions. |
| **data** | Object/Array | Yes | Application data payload. Returns {} or [] if no data is available. |
| **message** | String | Yes | Human-readable message for frontend display (e.g., "Operation Successful"). |
| **timestamp** | Long | Yes | Server-side current Unix timestamp. |

### Response Example
```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "code": 20000,
  "data": { "task_id": "0892f506-4087-4d7e-b890-21303145b4ee" },
  "message": "Operation Successful",
  "timestamp": 167890123
}
```
---

## Status Codes and Task

### HTTP Status Codes (Network Layer)
| Code | Meaning | Frontend Handling Suggestion |
| :--- | :--- | :--- |
| 200 | OK | Proceed to parse Application Layer code. |
| 201 | Created | Resource successfully created and persisted in the database. |
| 202 | Accepted | Task accepted for the backend. |
| 401 | Unauthorized | Token expired; clear local storage and redirect to Login. |
| 403 | Forbidden | Insufficient permissions for this resource. |
| 422 | Unprocessable Entity | Parameter validation failed (e.g., wrong file format). |
| 500 | Server Error | System crash; display "Server is busy, please try again". |

### Application Layer Codes (code field)
| Application Code | Semantic Meaning | Description |
| :--- | :--- | :--- |
| 20000 | SUCCESS | Task submitted or query successful. |
| 40001 | AUTH_FAILED | Invalid username or password. |
| 50001 | FILE_TYPE_ERROR | Unsupported file format (Allowed: mp4, mov, jpg, png, pdf). |
| 50002 | TASK_NOT_FOUND | Task ID does not exist or has expired. |
| 50003 | PROCESS_FAILED | Internal processing error (e.g., transcoding failed). |

---
### Task Lifecycle & Status Enum
The `status` field in the response follow this lifecycle:

| Status | Meaning | Frontend Action |
| :--- | :--- | :--- |
| PENDING | Task record created in DB. | Continue Polling. |
| QUEUED | Task is in the background queue, waiting for a worker. | Continue Polling. |
| PROCESSING | Task is currently being handled (e.g., transcoding). | Continue Polling (Show progress if available). |
| COMPLETED | Task finished successfully. | Stop Polling & Show Result. |
| FAILED | Task encountered an error. | Stop Polling & Show Error Message. |

### State Transition Diagram
```mermaid
stateDiagram-v2
    direction LR
    [*] --> PENDING: Submit Task
    PENDING --> QUEUED: Initialized
    QUEUED --> PROCESSING: Worker Picked Up
    PROCESSING --> COMPLETED: Success
    PROCESSING --> FAILED: Error
    FAILED --> [*]
    COMPLETED --> [*]
```

## API Endpoints

### Get Task List

* URL: /api/v1/task/list

* Method: GET

* Pattern: SYNC

Query Parameters:
| Parameter | Type    | Required | Default | Description                                         |
| :-------- | :------ | :------- | :------ | :-------------------------------------------------- |
| `status`  | string  | No       | None    | Filter by: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `limit`   | integer | No       | 100     | Max number of tasks to return (Min: 1, Max: 1000)   |

Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/task/list?status=COMPLETED&limit=2'
```
Response (200 OK)
```json
{
    "code": 20000,
    "data": [
        {
            "status": "COMPLETED",
            "payload": {
                "source": "minio",
                "file_key": "runs/f52c2905-fb78-4ddd-a89e-9fb673546740/raw/application/default/apple_loop100.h265",
                "bucket": "content-search",
                "filename": "apple_loop100.h265",
                "run_id": "f52c2905-fb78-4ddd-a89e-9fb673546740"
            },
            "result": {
                "message": "File from MinIO successfully processed. db returns {}"
            },
            "progress": 0,
            "task_type": "file_search",
            "id": "56cc417c-9524-41a9-a500-9f0c44a05eac",
            "user_id": "admin",
            "created_at": "2026-03-24T12:50:34.281421"
        },
        {
            "status": "COMPLETED",
            "payload": {
                "source": "minio",
                "file_key": "runs/2949cc0e-a1aa-4001-aa0f-8f42a36c3e7c/raw/application/default/apple_loop100.h265",
                "bucket": "content-search",
                "filename": "apple_loop100.h265",
                "run_id": "2949cc0e-a1aa-4001-aa0f-8f42a36c3e7c"
            },
            "result": {
                "message": "File from MinIO successfully processed. db returns {}"
            },
            "progress": 0,
            "task_type": "file_search",
            "id": "8032db45-129b-4474-8d58-122f33661f19",
            "user_id": "admin",
            "created_at": "2026-03-24T12:48:13.301178"
        }
    ],
    "message": "Success",
    "timestamp": 1774330753
}
```
### Task Status Polling
Used to track the progress and retrieve the final result of a submitted task.

* URL: /api/v1/task/query/{task_id}

* Method: GET

* Pattern: SYNC

Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/task/query/56cc417c-9524-41a9-a500-9f0c44a05eac'
```

Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "task_id": "e557b305-e37c-4074-a04a-ebd067efbd5d",
        "status": "COMPLETED",
        "progress": 100,
        "result": {
            "message": "File from MinIO successfully processed. db returns {'visual': {'insert_count': 1}}",
            "video_summary": {
                "type": "done",
                "job_id": "bc6513aa-e118-4945-84a8-02922595044e",
                "run_id": "5e405f58-03cf-4e44-9e10-85741283587a",
                "asset_id": "classroom_8.mp4",
                "total_chunks": 1,
                "succeeded_chunks": 1,
                "failed_chunks": 0,
                "ingest_ok_chunks": 1,
                "ingest_failed_chunks": 0,
                "elapsed_seconds": 36.89442276954651
            }
        }
    },
    "message": "Query successful",
    "timestamp": 1774879431
}
```

### File Upload
Used to upload a video file and initiate an asynchronous background task.

* URL: /api/v1/object/upload
* Method: POST
* Content-Type: multipart/form-data
* Payload: file (Binary)
* Pattern: ASYNC

Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/object/upload' \
--form 'file=@"/C:/videos/videos/car-detection-2min.mp4"'
```
Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "task_id": "c68211de-2187-4f52-b47d-f3a51a52b9ca",
        "status": "QUEUED"
    },
    "message": "File received, processing started.",
    "timestamp": 1773909147
}
```

### File ingestion
* URL: /api/v1/object/ingest
* Method: POST
* Pattern: ASYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| file_key | string | Yes | The full path of the file in MinIO (excluding bucket name). |
| bucket_name | string | No | The MinIO bucket name. Defaults to content-search. |
| prompt | string | No | Instructions for the AI (VLM). Defaults to "Please summarize this video." |
| chunk_duration | integer | No | Duration of each video segment in seconds. Defaults to 30. |
| meta | object | No | Custom metadata (e.g., {"tags": ["lecture"]}). Used for filtering during search. |

Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/object/ingest' \
--header 'Content-Type: application/json' \
--data '{
    "bucket_name": "content-search", 
    "file_key": "runs/c9a34e33-284a-48af-8d41-2b0d7d2989a7/raw/video/default/classroom_8.mp4"
}'
```
Response:
```json
{
    "code": 20000,
    "data": {
        "task_id": "44e339fb-3306-41b8-b1e1-4ecae7ce0ada",
        "status": "PROCESSING",
        "file_key": "runs/c9a34e33-284a-48af-8d41-2b0d7d2989a7/raw/video/default/classroom_8.mp4"
    },
    "message": "Ingestion process started for existing file",
    "timestamp": 1774878031
}
```

### File upload ana ingestion
* URL: /api/v1/object/upload-ingest
* Method: POST
* Content-Type: multipart/form-data
* Pattern: ASYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| file | Binary | Yes | The video file to be uploaded. |
| prompt | string | No | Summarization instructions (passed as a Form field). |
| chunk_duration | integer | No | Segment duration in seconds (passed as a Form field). |
| meta | string | No | JSON string of metadata (e.g., '{"course": "CS101"}'). |

Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/object/upload-ingest' \
--form 'file=@"/C:/videos/videos/classroom_8.mp4"' \
--form 'meta="{\"tags\": [\"class\"], \"course\": \"CS101\", \"semester\": \"Spring 2026\"}"'
```
Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "task_id": "559814ae-cef6-475c-9a79-3819549228d9",
        "status": "PROCESSING",
        "file_key": "runs/a955dbfc-59eb-4e40-953f-0cfe55e54464/raw/video/default/classroom_8.mp4"
    },
    "message": "Upload and Ingest started",
    "timestamp": 1774878113
}
```

### Retrieve and Search
* URL: /api/v1/object/search
* Method: POST
* Content-Type: multipart/form-data
* Pattern: ASYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| query | string | Either | Natural language search query (e.g., "student at desk"). |
| image_base64 | string | Either | Base64 encoded image string for visual similarity search. |
| max_num_results | integer | No | Maximum number of results to return. Defaults to 10. |
| filter | object | No | Metadata filters (e.g., {"run_id": "...", "tags": ["class"]}). |

Request:
```json
curl --location 'http://127.0.0.1:9011/api/v1/object/search' \
--header 'Content-Type: application/json' \
--data '{
    "query": "student in classroom",
    "max_num_results": 1,
    "filter": {
        "tags": ["classroom", "student"]
    }
}'
```
Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "results": [
            {
                "id": "1680138485034402529",
                "distance": 0.47685748,
                "meta": {
                    "start_frame": 0,
                    "chunk_text": "The video depicts a classroom setting with four individuals seated at desks arranged in a U-shape. The room has a modern design with blue chairs, white tables, and a whiteboard on the right side. The walls are adorned with various posters and a large mirror reflecting part of the room. The lighting is bright, creating a well-lit environment. The individuals appear to be engaged in a discussion or presentation, with one person standing and gesturing towards the others. The overall atmosphere suggests an educational or collaborative activity taking place.",
                    "reused": false,
                    "start_time": 0.0,
                    "asset_id": "classroom_8.mp4",
                    "file_path": "minio://content-search/runs/81802f9e-0a28-4486-bad2-2e05c1086326/derived/video/classroom_8.mp4/chunksum-v1/summaries/chunk_0001/summary.txt",
                    "run_id": "81802f9e-0a28-4486-bad2-2e05c1086326",
                    "type": "document",
                    "end_time": 0.32,
                    "summary_minio_key": "runs/81802f9e-0a28-4486-bad2-2e05c1086326/derived/video/classroom_8.mp4/chunksum-v1/summaries/chunk_0001/summary.txt",
                    "doc_filetype": "text/plain",
                    "chunk_id": "chunk_0001",
                    "minio_video_key": "runs/c9a34e33-284a-48af-8d41-2b0d7d2989a7/raw/video/default/classroom_8.mp4",
                    "chunk_index": 0,
                    "tags": [
                        "class",
                        "student"
                    ],
                    "end_frame": 8
                }
            }
        ]
    },
    "message": "Search completed",
    "timestamp": 1774877744
}
```
### Resource Download (Video/Image/Document)
Download existing resources in Minio.

* URL: /api/v1/object/download/{resource_id}
* Method: GET
* Pattern: SYNC
Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/object/download?file_key=runs%2Fc9a34e33-284a-48af-8d41-2b0d7d2989a7%2Fraw%2Fvideo%2Fdefault%2Fclassroom_8.mp4' \
--header 'Content-Type: application/json'
```

