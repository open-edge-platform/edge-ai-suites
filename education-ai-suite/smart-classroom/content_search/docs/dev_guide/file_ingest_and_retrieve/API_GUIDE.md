# File Ingest & Retrieve — API Guide

Base URL: `http://<host>:9990`

---

## Table of Contents

1. [Health Checks](#health-checks)
2. [Service Info](#service-info)
3. [Ingest Files](#ingest-files)
   - [Ingest a single file from MinIO](#ingest-a-single-file-from-minio)
   - [Ingest a directory from MinIO](#ingest-a-directory-from-minio)
   - [Ingest raw text](#ingest-raw-text)
4. [Query Indexed Files](#query-indexed-files)
5. [Delete Files from Index](#delete-files-from-index)
6. [Clear the Entire Index](#clear-the-entire-index)
7. [File and Embedding ID Maps](#file-and-embedding-id-maps)
   - [Get ID Maps](#get-id-maps)
   - [Recover ID Maps](#recover-id-maps)
8. [Retrieval](#retrieval)

---

## Health Checks

### `GET /v1/dataprep/health`

Check that the data preparation service is running.

**Request**

```bash
curl http://localhost:9990/v1/dataprep/health
```

**Response**

```json
{ "status": "healthy" }
```

---

### `GET /v1/retrieval/health`

Check that the retrieval service is running.

**Request**

```bash
curl http://localhost:9990/v1/retrieval/health
```

**Response**

```json
{ "status": "healthy" }
```

---

## Service Info

### `GET /v1/dataprep/info`

Returns the current state of the service — collection names, database init status, and MinIO connectivity.

**Request**

```bash
curl http://localhost:9990/v1/dataprep/info
```

**Response**

```json
{
  "visual_collection_name": "visual_data",
  "document_collection_name": "visual_data_documents",
  "visual_db_inited": true,
  "document_db_inited": true,
  "minio_connected": true
}
```

---

## Ingest Files

Files must first be uploaded to MinIO before they can be ingested. The service downloads the file, extracts embeddings, and stores them in ChromaDB.

**Supported file types:** `.jpg`, `.png`, `.jpeg`, `.mp4`, `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`, `.html`, `.htm`, `.xml`, `.md`

### `POST /v1/dataprep/ingest`

---

#### Ingest a single file from MinIO

**Request body**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bucket_name` | string | Yes | — | MinIO bucket name |
| `file_path` | string | Yes | — | Path to the file inside the bucket |
| `meta` | object | No | `{}` | Extra metadata to store alongside the file |
| `frame_extract_interval` | integer | No | `15` | For video files: extract a frame every N frames |
| `do_detect_and_crop` | boolean | No | `false` | Run object detection and crop detected regions before embedding |

**Example**

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "file_path": "documents/report.pdf"
  }'
```

With optional metadata and video settings:

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "file_path": "videos/lecture.mp4",
    "meta": { "course": "CS101", "semester": "Spring 2026" },
    "frame_extract_interval": 30,
    "do_detect_and_crop": true
  }'
```

With list-valued metadata fields:

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "file_path": "documents/report.pdf",
    "meta": {
      "tags": ["finance", "quarterly", "2026"],
      "authors": ["Alice", "Bob"],
      "year": 2026
    }
  }'
```

> **Note:** Metadata values can be strings, numbers, booleans, or **homogeneous lists** (all elements must be the same type). The `tags` field, if provided, must be a **list of strings** — passing a non-list or a list with non-string elements returns `422`.

**Response**

```json
{ "message": "File from MinIO successfully processed. db returns ..." }
```

---

#### Ingest a directory from MinIO

Ingests all supported files found under a given folder prefix in MinIO.

**Request body**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bucket_name` | string | Yes | — | MinIO bucket name |
| `folder_path` | string | Yes | — | Folder prefix inside the bucket |
| `meta` | object | No | `{}` | Extra metadata applied to every file ingested from the directory |
| `frame_extract_interval` | integer | No | `15` | For video files: extract a frame every N frames |
| `do_detect_and_crop` | boolean | No | `false` | Run object detection and crop detected regions before embedding |

**Example**

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "folder_path": "course-materials/week1/"
  }'
```

With list-valued metadata applied to every file in the directory:

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "folder_path": "course-materials/week1/",
    "meta": {
      "course": "CS101",
      "topics": ["arrays", "linked lists", "sorting"],
      "week": 1
    }
  }'
```

**Response**

```json
{ "message": "Files from MinIO directory successfully processed. db returns ..." }
```

> **Tip:** The service distinguishes between a single-file request and a directory request based on the presence of `file_path` vs `folder_path`.

---

#### Ingest raw text

### `POST /v1/dataprep/ingest_text`

Embeds a raw text string as a **single node** (no chunking) and stores it in the document collection. Use this when you already have clean, pre-processed text and want to skip file parsing entirely.

**Request body**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | — | Raw text content to embed and store |
| `bucket_name` | string | No | — | MinIO bucket name (used to build the `file_path` identifier) |
| `file_path` | string | No | — | Logical path inside the bucket (used to build the `file_path` identifier) |
| `meta` | object | No | `{}` | Extra metadata to store alongside the text |

**Example**

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest_text \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "file_path": "summaries/lecture1.txt",
    "text": "Photosynthesis is the process by which plants convert light into energy.",
    "meta": { "course": "CS101", "source": "summary" }
  }'
```

With tags metadata:

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest_text \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "content-search",
    "file_path": "summaries/lecture1.txt",
    "text": "Photosynthesis is the process by which plants convert light into energy.",
    "meta": {
      "tags": ["biology", "plants", "energy"],
      "related_chapters": [3, 4],
      "course": "BIO101"
    }
  }'
```

> Note: The `tags` field must be a **list of strings** — passing a non-list or a list with non-string elements returns `422`.

Below metadatas shall be automatically appended
```json
"meta": {
  "chunk_index": 0,
  "chunk_text": "text",
  "type": "document",
  "doc_filetype": "text/plain",
}
```

**Response**

```json
{ "message": "Text successfully ingested. db returns ..." }
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | `text` is empty or missing |
| `422` | `tags` in `meta` is not a list of strings |
| `500` | Embedding or database error |

---

## Query Indexed Files

### `GET /v1/dataprep/get`

Look up all indexed entries for a specific file.

**Query parameter**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | The MinIO URI of the file, e.g. `minio://bucket/path/file.pdf` |

**Example**

```bash
curl "http://localhost:9990/v1/dataprep/get?file_path=minio://my-bucket/documents/report.pdf"
```

**Response**

```json
{
  "file_path": "minio://my-bucket/documents/report.pdf",
  "ids_in_db": ["id-1", "id-2", "id-3"]
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | `file_path` is missing or not a string |
| `404` | Path scheme is not `minio://` or `http(s)://` |
| `200` | File embedding not found in the database (not yet ingested, or id_map out of sync — call `POST /v1/dataprep/recover` to resync) |

---

## Delete Files from Index

### `DELETE /v1/dataprep/delete`

Remove all indexed entries for a specific file. **The original file in MinIO is not deleted.**

**Query parameter**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | The MinIO URI of the file to remove from the index |

**Example**

```bash
curl -X DELETE "http://localhost:9990/v1/dataprep/delete?file_path=minio://my-bucket/documents/report.pdf"
```

**Response**

```json
{
  "message": "File successfully deleted. db returns: ...",
  "removed_ids": ["id-1", "id-2", "id-3"]
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | `file_path` is missing or not a string |
| `404` | Path scheme is not `minio://` or `http(s)://` |
| `200` | File embedding not found in the database (not yet ingested, or id_map out of sync — call `POST /v1/dataprep/recover` to resync) |

---

## Clear the Entire Index

### `DELETE /v1/dataprep/delete_all`

Remove **all** entries from the database. **Original files in MinIO are not deleted.**

**Example**

```bash
curl -X DELETE http://localhost:9990/v1/dataprep/delete_all
```

**Response**

```json
{ "message": "Database successfully cleared. db returns: ..." }
```

---

## File and Embedding ID Maps

### Get ID Maps

`GET /v1/dataprep/list`

Returns the current in-memory id_maps without modifying anything. Use this to inspect which file paths and DB IDs are currently tracked.

**Request**

```bash
curl http://localhost:9990/v1/dataprep/list
```

**Response**

```json
{
  "visual": {
    "minio://my-bucket/images/photo.jpg": ["2001"]
  },
  "document": {
    "minio://my-bucket/docs/report.pdf": ["1001", "1002", "1003"]
  }
}
```

---

### Recover ID Maps

`POST /v1/dataprep/recover`

Clears and rebuilds the in-memory id_maps by re-querying both ChromaDB collections. Use this when `GET /v1/dataprep/get` or `DELETE /v1/dataprep/delete` returns an unexpected "not found" message for a file that was previously ingested — which can happen after a server restart, a crash mid-ingest, or any direct modification of the database outside this service.

**Request**

```bash
curl -X POST http://localhost:9990/v1/dataprep/recover
```

**Response**

```json
{
  "message": "ID maps successfully recovered from database.",
  "recovered": {
    "visual_files": 12,
    "document_files": 5
  }
}
```

- `visual_files` — number of distinct file paths recovered into the visual id_map
- `document_files` — number of distinct file paths recovered into the document id_map

> **Note:** POST is write-only with respect to in-memory state — it rebuilds the id_maps from the database but does not modify any stored data.

---

## Retrieval

### `POST /v1/retrieval`

Search the index using a text query or a base64-encoded image. Returns the top-k most similar results from both the visual and document collections.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | One of `query` or `image_base64` | Natural language search query |
| `image_base64` | string | One of `query` or `image_base64` | Base64-encoded image to search by visual similarity |
| `filter` | object | No | Metadata filter to narrow results. Scalar fields use direct equality; list fields (e.g. `tags`) is parsed as `"or"`. |
| `max_num_results` | integer | No (default `10`) | Max results per collection (1–16384). For text queries, up to `2 × max_num_results` may be returned (top-k from visual collection + top-k from document collection, merged and sorted by distance). For image queries, at most `max_num_results` are returned. |

> **Note:** Provide exactly one of `query` or `image_base64` — not both.

> **For Developer** A placeholder of list fields parsed as `"and"` is added.

**Text search example**

```bash
curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d '{
    "query": "photosynthesis diagram",
    "max_num_results": 5
  }'
```

**Image search example**

```bash
# Encode an image to base64 first
IMAGE_B64=$(base64 -w 0 my_image.jpg)

curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d "{
    \"image_base64\": \"$IMAGE_B64\",
    \"max_num_results\": 5
  }"
```

**Filtered search example**

```bash
curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d '{
    "query": "lecture notes",
    "filter": { "course": "CS101", "tags": ["biology", "plants"] },
    "max_num_results": 3
  }'
```

Returns results of course "CS101" whose `tags` array contains `"biology"` **or** `"plants"`

**Response**

```json
{
  "results": [
    {
      "id": "abc123",
      "distance": 0.142,
      "meta": {
        "file_path": "minio://my-bucket/documents/report.pdf",
        "page": 3,
        "course": "CS101",
        "tags": ["plants"]
      }
    },
    ...
  ]
}
```

- `id` — unique identifier of the indexed chunk/frame
- `distance` — similarity distance (lower = more similar)
- `meta` — metadata stored at ingest time, including the original `file_path`

---

## Error Responses

All endpoints return standard HTTP status codes:

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad request — invalid or missing parameters |
| `404` | Not found — bucket or file does not exist |
| `422` | Unprocessable request body |
| `500` | Internal server error |

Error responses include a `detail` field:

```json
{ "detail": "Bucket my-bucket not found." }
```
