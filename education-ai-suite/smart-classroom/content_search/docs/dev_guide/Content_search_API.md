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
  "data": { "task_id": "0892f506-4087-4d7e-b890-21303145b4ee", "status": "PROCESSING" },
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
| 20000 | SUCCESS | Task submitted, query successful, or cleanup completed. |
| 40000 | BAD_REQUEST | General logic error (e.g., trying to delete a processing task). |
| 40001 | AUTH_FAILED | Invalid username or password. |
| 40901 | FILE_ALREADY_EXISTS | File already existed (Hash exist). |
| 50001 | FILE_TYPE_ERROR | Unsupported file format (Allowed: mp4, mov, jpg, png, pdf). |
| 50002 | TASK_NOT_FOUND | Task ID does not exist or has expired. |
| 50003 | PROCESS_FAILED | Internal processing error (e.g., file system or DB delete failed). |

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
### Task endpoints
#### Get Task List

* URL: /api/v1/task/list

* Method: GET

* Pattern: SYNC

Query Parameters:
| Parameter | Type    | Required | Default | Description                                         |
| :-------- | :------ | :------- | :------ | :-------------------------------------------------- |
| `status`  | `string`  | No       | None    | Filter by: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `limit`   | `integer` | No       | 100     | Max number of tasks to return (Min: 1, Max: 1000)   |

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
                "source": "local",
                "file_key": "runs/f52c2905-fb78-4ddd-a89e-9fb673546740/raw/application/default/apple_loop100.h265",
                "bucket": "content-search",
                "filename": "apple_loop100.h265",
                "run_id": "f52c2905-fb78-4ddd-a89e-9fb673546740"
            },
            "result": {
                "message": "File successfully processed. db returns {}"
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
                "source": "local",
                "file_key": "runs/2949cc0e-a1aa-4001-aa0f-8f42a36c3e7c/raw/application/default/apple_loop100.h265",
                "bucket": "content-search",
                "filename": "apple_loop100.h265",
                "run_id": "2949cc0e-a1aa-4001-aa0f-8f42a36c3e7c"
            },
            "result": {
                "message": "File successfully processed. db returns {}"
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
#### Task Status Polling
Used to track the progress and retrieve the final result of a submitted task.

* URL: /api/v1/task/query/{task_id}

* Method: GET

* Pattern: SYNC

Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/task/query/6b9a6a55-d327-42fe-b05e-e0f3098fe797'
```

Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "task_id": "6b9a6a55-d327-42fe-b05e-e0f3098fe797",
        "status": "COMPLETED",
        "progress": 100,
        "result": {
            "message": "Upload only, no ingest requested",
            "file_info": {
                "source": "local",
                "file_key": "runs/9e96f16a-9689-4c25-a515-04a1040b193f/raw/text/default/phy_class.txt",
                "bucket": "content-search",
                "filename": "phy_class.txt",
                "run_id": "9e96f16a-9689-4c25-a515-04a1040b193f"
            }
        }
    },
    "message": "Query successful",
    "timestamp": 1774931711
}
```
### File Process
#### File Support Matrix

The system supports the following file formats for all ingestion and upload-ingest operations.

| Category | Supported Extensions | Processing Logic |
| :--- | :--- | :--- |
| **Video** | `.mp4` | Frame extraction, AI-driven summarization, and semantic indexing. |
| **Document** | `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls` | Full-text extraction, semantic chunking, and vector embedding. |
| **Web/Markup** | `.html`, `.htm`, `.xml`, `.md` | Structured text parsing and content indexing. |
| **Image** | `.jpg`, `.png`, `.jpeg` | Visual feature embedding and similarity search indexing. |

> **Technical Note**: 
> - **Video**: Default chunking is set to 30 seconds unless the `chunk_duration` parameter is provided.
> - **Text**: Automatic semantic segmentation is applied to ensure high-quality retrieval results.
> - **Max File Size**: Please refer to the `CS_MAX_CONTENT_LENGTH` environment variable (Default: 100MB).

#### File Upload
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
        "status": "PROCESSING"
    },
    "message": "File received, processing started.",
    "timestamp": 1773909147
}
```

#### File ingestion
* URL: /api/v1/object/ingest
* Method: POST
* Pattern: ASYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file_key` | `string` | Yes | The full path of the file in storage (excluding bucket name). |
| `bucket_name` | `string` | No | The storage bucket name. Defaults to content-search. |
| `prompt` | `string` | No | Instructions for the AI (VLM). Defaults to "Please summarize this video." |
| `chunk_duration` | `integer` | No | Duration of each video segment in seconds. Defaults to 30. |
| `meta` | `object` | No | Custom metadata (e.g., {"tags": ["lecture"]}). Used for filtering during search. |

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
#### Text file ingestion
Primarily processes raw text strings passed in the request body for semantic indexing. It also supports fetching content from existing text-based objects in storage.

* URL: /api/v1/object/ingest-text
* Method: POST
* Pattern: ASYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `text` | `string` | **Yes** | **Raw text content** to be segmented, embedded, and stored in the vector database. |
| `bucket_name` | `string` | No | Storage bucket name (used to logically group the data or build the identifier). |
| `file_path` | `string` | No | Logical path or filename (used as a unique identifier for the text source). |
| `meta` | `object` | No | Extra metadata to store alongside the text (e.g., `course`, `author`, `tags`). |

Request:
```
# example for raw text content
curl --location 'http://127.0.0.1:9011/api/v1/object/ingest-text' \
--header 'Content-Type: application/json' \
--data '{
    "text": "Newton'\''s Second Law of Motion states that the force acting on an object is equal to the mass of that object multiplied by its acceleration (F = ma). This relationship describes how the velocity of an object changes when it is subjected to an external force.",
    "meta": {
        "source": "topic-search"
    }
}'
```
Response:
```json
{
    "code": 20000,
    "data": {
        "task_id": "df3caeb3-3287-4e41-a1f0-098c90d08e03",
        "status": "PROCESSING"
    },
    "message": "Text ingestion task created successfully",
    "timestamp": 1775006765
}
```

#### File upload and ingestion
A unified workflow that first saves the file to local storage and then immediately initiates the ingestion pipeline. Features full content indexing and AI-driven Video Summarization for supported video formats.

* URL: /api/v1/object/upload-ingest
* Method: POST
* Content-Type: multipart/form-data
* Pattern: ASYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | `Binary` | Yes | The video file to be uploaded. |
| `prompt` | `string` | No | Summarization instructions (passed as a Form field). |
| `chunk_duration` | `integer` | No | Segment duration in seconds (passed as a Form field). |
| `meta` | `string` | No | JSON string of metadata (e.g., '{"course": "CS101"}'). |

* Example:
Request:
```
curl --location 'http://127.0.0.1:9011/api/v1/object/upload-ingest' \
--form 'file=@"/C:/videos/videos/classroom_8.mp4"' \
--form 'meta="{\"tags\": [\"class\"], \"course\": \"CS101\", \"semester\": \"Spring 2026\"}"'
```
Response (200 OK):
```json
// example 1: Normal upload and ingest
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
// example 2: File already exists, return the existed taskid
{
    "code": 40901,
    "data": {
        "file_hash": "080c00cf05bc7b31e2b1c4bcfc9b16a61b29608fdbfc5451d1cbd8eadbdd34cb",
        "file_name": "classroom_8.mp4",
        "created_at": "2026-04-14 14:33:53.107540",
        "task_id": "559814ae-cef6-475c-9a79-3819549228d9"
    },
    "message": "Upload failed: File already exists.",
    "timestamp": 1776148605
}
```

#### Retrieve and Search
Executes a similarity search across vector collections using either natural language queries or base64-encoded images. Returns ranked results with associated metadata and object references.

* URL: /api/v1/object/search
* Method: POST
* Content-Type: multipart/form-data
* Pattern: SYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `query` | `string` | Either | Natural language search query (e.g., "student at desk"). |
| `image_base64` | `string` | Either | Base64 encoded image string for visual similarity search. |
| `max_num_results` | `integer` | No | Maximum number of results to return. Defaults to 10. For text queries, up to `2 × max_num_results` may be returned (`top-k` from visual collection + `top-k` from document collection, merged and sorted by distance). For image queries, at most `max_num_results` are returned.|
| `filter` | `object` | No | Metadata filters (e.g., {"type": ["document"], "tags": ["class"]}), detail sees below |

* Filter Usage Detail

Different filter keys are always combined with `AND`. When a filter value is a `list`, the matching logic depends on the field type:

| Field type | Example fields | List behavior | Operator used |
| ---------- | -------------- | ------------- | ------------- |
| `Array metadata` | `tags` | Matches if the stored array contains **at least one** of the filter values | `$contains` |
| `Scalar metadata` | `type`, `course`, `semester` | Matches if the stored value **equals any** of the filter values | `$eq` (OR) |

| Note: Video-type results may appear even when "video" is not explicitly selected in the type filter, because relevant document summaries can be converted into video results during post-processing. These constructed results have "original_type": "constructed_from_summary" in their metadata to distinguish them from native video frame results.

* Example:
Request:
```
# Example 1: Filter by tags — returns results whose tags array contains "test_tag1" or "test_tag2"
curl --location 'http://127.0.0.1:9011/api/v1/object/search' \
--header 'Content-Type: application/json' \
--data '{
    "query": "classroom",
    "max_num_results": 2,
    "filter": {
        "tags": ["test_tag1", "test_tag2"]
    }
}'
# Example 2: Filter by type — available values: `video`, `image`, `document`. If not specified, all types are returned. Example returns only `video` or `document` results:
curl --location 'http://127.0.0.1:9011/api/v1/object/search' \
--header 'Content-Type: application/json' \
--data '{
    "query": "student in classroom",
    "max_num_results": 1,
    "filter": {
        "type": ["video", "document"]
    }
}'
```
Response (200 OK):
```json
{
    "code": 20000,
    "data": {
        "task_id": "4d3159df-93d1-44a9-8592-bc48eb561b05",
        "status": "COMPLETED",
        "results": [
            {
                "id": "197972195449837430",
                "distance": 0.8402439,
                "meta": {
                    "type": "video",
                    "file_path": "local://content-search/runs/2a6e14b6-da45-4e20-93a1-2291ab01d6f6/raw/video/default/store-aisle-detection.mp4",
                    "file_name": "store-aisle-detection.mp4",
                    "video_pin_second": 11.01,
                    "video_start_second": 7.76,
                    "video_end_second": 14.26,
                    "summary_text": "The video depicts a scene inside a store filled with shelves of white ceramic dishes, including bowls, plates, mugs, and cups. The store appears to be a pottery or ceramics shop, as evidenced by the variety of items available for purchase.\n\nIn the foreground, a man wearing a brown jacket is browsing through the shelves, examining the ceramic dishes. He seems interested in the selection and is carefully inspecting each item. Nearby, a woman in a green jacket is also looking at the dishes, possibly considering purchasing some. Another person, dressed in a blue jacket, is seen walking past the shelves, seemingly uninterested in the products.\n\nAs the camera pans around the store, more people can be observed engaging with the ceramic items. Some individuals are standing near the shelves, closely examining the dishes, while others are walking through the aisles, browsing the available options. The store has a well-lit environment, making it easy for customers to see the details of the ceramic pieces.\n\nThroughout the video, the focus remains on the interaction between the customers and the ceramic dishes, showcasing the variety of items available for purchase. The store's layout and organization allow customers to easily navigate through the aisles and find their desired items."
                },
                "score": 53.65
            },
            {
                "id": "435369449869751787",
                "distance": 0.7416173,
                "meta": {
                    "type": "image",
                    "file_path": "local://content-search/runs/7a4480af-3f9c-40b6-ac9e-0a698717bc45/raw/image/default/classroom.jpg",
                    "file_name": "classroom.jpg",
                    "tags": [
                        "img_tag1",
                        "img_tag2"
                    ]
                },
                "score": 83.56
            },
            {
                "id": "3898473585704952476",
                "distance": 0.19918823,
                "meta": {
                    "doc_filename": "ComputerScienceOne.pdf",
                    "doc_is_continuation": true,
                    "doc_last_modified": "2026-04-14T20:56:13",
                    "doc_sequence_number": 448,
                    "chunk_text": "tegral. Instead, Computer Science is the study of computers and computation. It involves studying and understanding computational processes and the development of algorithms and techniques and how they apply to problems.",
                    "chunk_index": 448,
                    "type": "document",
                    "doc_filetype": "application/pdf",
                    "doc_page_number": 36,
                    "doc_languages": "[\"eng\"]",
                    "doc_file_directory": "C:\\Users\\user\\AppData\\Local\\Temp\\tmpwma1e266",
                    "file_path": "local://content-search/runs/a6d3ef1f-510b-4ec9-8a16-4db2332758b0/raw/application/default/ComputerScienceOne.pdf",
                    "file_name": "ComputerScienceOne.pdf",
                    "tags": [
                        "pdf_tag1",
                        "pdf_tag2"
                    ]
                },
                "score": 99.81,
                "reranker_score": 6.28125
            }
        ]
    },
    "message": "Search completed",
    "timestamp": 1776171542
}
```
#### Resource Download (Video/Image/Document)
Download or preview existing resources from storage.

* URL: /api/v1/object/download
* Method: GET
* Pattern: SYNC
* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file_key` | `string` | Yes | The full path of the file in storage (e.g., "runs/xxx/raw/video/default/file.mp4"). |
| `inline` | `boolean` | No | If `true`, sets `Content-Disposition: inline` for browser preview (PDF, video, image). If `false` or omitted, forces download with `Content-Disposition: attachment`. Defaults to `false`. |

Request:
```bash
# Example 1: Download file (default behavior)
curl --location 'http://127.0.0.1:9011/api/v1/object/download?file_key=runs%2Fc9a34e33-284a-48af-8d41-2b0d7d2989a7%2Fraw%2Fvideo%2Fdefault%2Fclassroom_8.mp4'

# Example 2: Preview file in browser (PDF, video, image)
curl --location 'http://127.0.0.1:9011/api/v1/object/download?file_key=runs%2Fc9a34e33-284a-48af-8d41-2b0d7d2989a7%2Fraw%2Fapplication%2Fdefault%2Fdocument.pdf&inline=true'
```

**Usage Notes**:
- Use `inline=true` for embedding resources in `<iframe>`, `<video>`, or `<img>` tags for in-browser preview.
- Use `inline=false` (or omit) when you need to trigger a download prompt in the browser.

#### Cleanup file storage and record
Removes all physical and logical footprints associated with a specific task, including local storage files, indexed vectors in ChromaDB, and metadata records in the database.

* URL: /api/v1/object/cleanup-task/{task_id}

* Method: DELETE

* Pattern: SYNC

* Parameters:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `task_id` | `string` | Yes | The unique identifier (UUID) of the task to be cleaned up. |

Request:
```powershell
curl --location --request DELETE 'http://127.0.0.1:9011/api/v1/object/cleanup-task/b14b0c14-e768-4536-9d13-ea556f9adc1b'
```
Response:
```json
// example 1: 200 OK - Success
{
    "code": 20000,
    "data": {
        "task_id": "b14b0c14-e768-4536-9d13-ea556f9adc1b",
        "status": "COMPLETED"
    },
    "message": "Cleanup completed",
    "timestamp": 1775723734
}
// example 2: 200 OK - Task Processing
{
    "code": 40000,
    "data": {},
    "message": "Task is still processing and cannot be deleted",
    "timestamp": 1775723800
}
// example 3: 200 OK - Task Not Found
{
    "code": 50002,
    "data": {},
    "message": "Task ID does not exist or has expired",
    "timestamp": 1775723850
}
```