# API Reference Guide - Video Processing Service

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

## Status Codes

### HTTP Status Codes (Network Layer)
| Code | Meaning | Frontend Handling Suggestion |
| :--- | :--- | :--- |
| 200 | OK | Proceed to parse Application Layer code. |
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

## Core Endpoints
### Architecture Note
All endpoints listed below are implemented using a **Synchronous (Sync)** blocking pattern on the server side. To handle long-running background tasks (such as video processing), the system utilizes a **Client-side Polling** mechanism. The backend will immediately return a `task_id` upon submission, and the Frontend is responsible for initiating subsequent status queries.

### Task Lifecycle & Status Enum
The `status` field in the response follow this lifecycle:

| Status | Meaning | Frontend Action |
| :--- | :--- | :--- |
| PENDING | Task record created in DB. | Continue Polling. |
| QUEUED | Task is in the background queue, waiting for a worker. | Continue Polling. |
| PROCESSING | Task is currently being handled (e.g., transcoding). | Continue Polling (Show progress if available). |
| COMPLETED | Task finished successfully. | Stop Polling & Show Result. |
| FAILED | Task encountered an error. | Stop Polling & Show Error Message. |
#### State Transition Diagram
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
### Endponts table

| Endpoint | Method | Pattern | Description | Status |
| :--- | :---: | :---: | :--- | :---: |
| `/api/v1/system/health` | **GET** | SYNC | Backend app health check | DONE |
| `/api/v1/task/{task_id}` | **GET** | SYNC | Query status of a specific task | DONE |
| `/api/v1/task/tasks` | **GET** | SYNC | Query tasks by conditions (e.g., `?status=PROCESSING`) | WIP |
| `/api/v1/task/cancel/{task_id}` | **POST** | SYNC | Cancel a running task | WIP |
| `/api/v1/task/pause/{task_id}` | **POST** | SYNC | Pause a running task | WIP |
| `/api/v1/task/resume/{task_id}` | **POST** | SYNC | Resume a paused task | WIP |
| `/api/v1/media/files` | **GET** | SYNC | Query files in MinIO with filters | DONE |
| `/api/v1/media/upload` | **POST** | ASYNC | Upload a file to MinIO | DONE |
| `/api/v1/media/ingest` | **POST** | ASYNC | Ingest a specific file from MinIO | WIP |
| `/api/v1/media/upload-ingest` | **POST** | ASYNC | Upload to MinIO and trigger ingestion | DONE |
| `/api/v1/media/search` | **POST** | ASYNC | Search for files based on description | DONE |
| `/api/v1/media/download` | **POST** | STREAM | Download file from MinIO | DONE |
| `/api/v1/video/summarization` | **POST** | STREAM | Generate video summarization | WIP |

### Task Status Polling
Used to track the progress and retrieve the final result of a submitted task.

* URL: /api/v1/task/{task_id}

* Method: GET

* Pattern: SYNC

Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "task_id": "371109e5-d374-4064-ba72-8f61b999d824",
        "status": "COMPLETED",
        "progress": 100,
        "result": {
            "summary": "This is a mock result from the local Dummy service for None.",
            "confidence": 0.98,
            "provider": "Mock-Windows-Service"
        }
    },
    "message": "Query successful",
    "timestamp": 1773907521
}
```

### File Upload
Used to upload a video file and initiate an asynchronous background task.

* URL: /api/v1/media/upload
* Method: POST
* Content-Type: multipart/form-data
* Payload: file (Binary)
* Pattern: ASYNC

Request:
```
curl --location 'http://127.0.0.1:8000/api/v1/file-upload' \
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
* URL: /api/v1/media/ingest
* Method: POST
* Pattern: ASYNC


### File upload ana ingestion
* URL: /api/v1/media/upload-ingest
* Method: POST
* Content-Type: multipart/form-data
* Pattern: ASYNC
  
```json
{
    "code": 20000,
    "data": {
        "task_id": "e458add3-bf5c-48f1-9593-4b72481bdca5",
        "status": "QUEUED",
        "file_key": "runs/5a477a66-bf88-4ebb-8cb6-0058811f5836/raw/video/default/car-detection-2min.mp4"
    },
    "message": "Upload and Ingest started",
    "timestamp": 1773909831
}
```
### Resource Lookup (Video/Image/Document)
Retrieve file metadata or direct access links for existing resources.

* URL: /api/v1/media/files/{resource_id}
* Method: GET
* Pattern: SYNC

Response (200 OK):
```json
{
  "code": 20000,
  "data": {
    "resource_id": "res-999",
    "type": "video",
    "name": "tutorial_01.mp4",
    "url": "https://cdn.example.com/files/tutorial_01.mp4",
    "created_at": 1709184000
  },
  "message": "Resource found",
  "timestamp": 1709184100
}
```
---

## Implementation Guidelines for Frontend

1. Polling Strategy: After receiving a task_id, start polling the Status Endpoint every 3 seconds. If the task is not finished after 1 minute, you may decrease the frequency to every 10 seconds.
2. Persistence: Store active task_ids in sessionStorage or localStorage. This allows the UI to resume polling if the user refreshes the page.
3. Error States: If status returns failed, stop polling immediately and display the message to the user.