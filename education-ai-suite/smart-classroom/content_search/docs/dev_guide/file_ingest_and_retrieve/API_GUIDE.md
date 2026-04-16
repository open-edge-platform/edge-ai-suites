# File Ingest & Retrieve — API Guide

Base URL: `http://<host>:9990`

---

## Table of Contents

1. [Health Checks](#health-checks)
   - [GET /v1/dataprep/health](#get-v1dataprep-health)
   - [GET /v1/retrieval/health](#get-v1retrieval-health)
2. [Service Info](#service-info)
   - [GET /v1/dataprep/info](#get-v1dataprep-info)
3. [Ingest Files](#ingest-files)
   - [POST /v1/dataprep/ingest](#post-v1dataprep-ingest)
   - [POST /v1/dataprep/ingest_text](#post-v1dataprep-ingest_text)
4. [Query Indexed Files](#query-indexed-files)
   - [GET /v1/dataprep/get](#get-v1dataprep-get)
5. [Delete Files from Index](#delete-files-from-index)
   - [DELETE /v1/dataprep/delete](#delete-v1dataprep-delete)
   - [DELETE /v1/dataprep/delete_by_ids](#delete-v1dataprep-delete_by_ids) (developer-only)
6. [Clear the Entire Index](#clear-the-entire-index)
   - [DELETE /v1/dataprep/delete_all](#delete-v1dataprep-delete_all)
7. [File and Embedding ID Maps](#file-and-embedding-id-maps)
   - [GET /v1/dataprep/list](#get-v1dataprep-list)
   - [POST /v1/dataprep/recover](#post-v1dataprep-recover)
8. [Retrieval](#retrieval)
   - [POST /v1/retrieval](#post-v1retrieval)
   - [POST /v1/retrieval/image](#post-v1retrieval-image) (developer-only)

---

## Health Checks

### GET /v1/dataprep/health

Check that the data preparation service is running.

**Request**

```bash
curl http://localhost:9990/v1/dataprep/health
```

#### Response

```json
{ "status": "healthy" }
```

---

### GET /v1/retrieval/health

Check that the retrieval service is running.

**Request**

```bash
curl http://localhost:9990/v1/retrieval/health
```

#### Response

```json
{ "status": "healthy" }
```

---

## Service Info

### GET /v1/dataprep/info

Returns the current state of the service — collection names, database init status, and storage connectivity.

**Request**

```bash
curl http://localhost:9990/v1/dataprep/info
```

#### Response

```json
{
  "visual_collection_name": "visual_data",
  "document_collection_name": "visual_data_documents",
  "visual_db_inited": true,
  "document_db_inited": true,
  "storage_available": true
}
```

---

## Ingest Files

Files must first be uploaded to storage before they can be ingested. The service downloads the file, extracts embeddings, and stores them in ChromaDB.

**Supported file types:** `.jpg`, `.png`, `.jpeg`, `.mp4`, `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`, `.html`, `.htm`, `.xml`, `.md`

### POST /v1/dataprep/ingest

Ingest a single file or a directory from storage.

#### Request body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bucket_name` | string | Yes | — | storage bucket name |
| `file_path` | string | Yes | — | Path to the file inside the bucket |
| `meta` | object | No | `{}` | Extra metadata to store alongside the file |


#### Example

```bash
curl -X POST http://localhost:9990/v1/dataprep/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-bucket",
    "file_path": "videos/lecture.mp4",
    "meta": { "course": "CS101", "semester": "Spring 2026" }
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

#### Response

```json
{ "message": "File successfully processed. db returns ..." }
```

---

Ingest a directory from storage. All supported files found under a given folder prefix will be processed.

#### Request body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bucket_name` | string | Yes | — | storage bucket name |
| `folder_path` | string | Yes | — | Folder prefix inside the bucket |
| `meta` | object | No | `{}` | Extra metadata applied to every file ingested from the directory |

#### Example

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

#### Response

```json
{ "message": "Files from storage directory successfully processed. db returns ..." }
```

> **Tip:** The service distinguishes between a single-file request and a directory request based on the presence of `file_path` vs `folder_path`.

---

## Ingest raw text

### POST /v1/dataprep/ingest_text

Embeds a raw text string as a **single node** (no chunking) and stores it in the document collection. Use this when you already have clean, pre-processed text and want to skip file parsing entirely.

#### Request body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | — | Raw text content to embed and store |
| `bucket_name` | string | No | — | storage bucket name (used to build the `file_path` identifier) |
| `file_path` | string | No | — | Logical path inside the bucket (used to build the `file_path` identifier) |
| `meta` | object | No | `{}` | Extra metadata to store alongside the text |

#### Example

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

#### Response

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

### GET /v1/dataprep/get

Look up all indexed entries for a specific file.

**Query parameter**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | The storage URI of the file, e.g. `local://bucket/path/file.pdf` |

#### Example

```bash
curl "http://localhost:9990/v1/dataprep/get?file_path=local://my-bucket/documents/report.pdf"
```

#### Response

```json
{
  "file_path": "local://my-bucket/documents/report.pdf",
  "ids_in_db": ["id-1", "id-2", "id-3"]
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | `file_path` is missing or not a string |
| `404` | Path scheme is not `local://` or `http(s)://` |
| `200` | File embedding not found in the database (not yet ingested, or id_map out of sync — call `POST /v1/dataprep/recover` to resync) |

---

## Delete Files from Index

### DELETE /v1/dataprep/delete

Remove all indexed entries for a specific file. **The original file in storage is not deleted.**

**Query parameter**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | The storage URI of the file to remove from the index |

#### Example

```bash
curl -X DELETE "http://localhost:9990/v1/dataprep/delete?file_path=local://my-bucket/documents/report.pdf"
```

#### Response

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
| `404` | Path scheme is not `local://` or `http(s)://` |
| `200` | File embedding not found in the database (not yet ingested, or id_map out of sync — call `POST /v1/dataprep/recover` to resync) |

---

## Clear the Entire Index

### DELETE /v1/dataprep/delete_all

Remove **all** entries from the database. **Original files in storage are not deleted.**

#### Example

```bash
curl -X DELETE http://localhost:9990/v1/dataprep/delete_all
```

#### Response

```json
{ "message": "Database successfully cleared. db returns: ..." }
```

---

## File and Embedding ID Maps

### GET /v1/dataprep/list

Returns the current in-memory id_maps without modifying anything. Use this to inspect which file paths and DB IDs are currently tracked.

**Request**

```bash
curl http://localhost:9990/v1/dataprep/list
```

#### Response

```json
{
  "visual": {
    "local://my-bucket/images/photo.jpg": ["2001"]
  },
  "document": {
    "local://my-bucket/docs/report.pdf": ["1001", "1002", "1003"]
  }
}
```

---

### POST /v1/dataprep/recover

Clears and rebuilds the in-memory id_maps by re-querying both ChromaDB collections. Use this when `GET /v1/dataprep/get` or `DELETE /v1/dataprep/delete` returns an unexpected "not found" message for a file that was previously ingested — which can happen after a server restart, a crash mid-ingest, or any direct modification of the database outside this service.

**Request**

```bash
curl -X POST http://localhost:9990/v1/dataprep/recover
```

#### Response

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

### POST /v1/retrieval

Search the index using a text query or a base64-encoded image. Returns the top-k most similar results from both the visual and document collections.

#### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | One of `query` or `image_base64` | Natural language search query |
| `image_base64` | string | One of `query` or `image_base64` | Base64-encoded image to search by visual similarity |
| `filter` | object | No | Metadata filter to narrow results (see [Filter usage](#filter-usage) below). |
| `max_num_results` | integer | No (default `10`) | Max results per collection (1–16384). For text queries, up to `2 × max_num_results` may be returned (top-k from visual collection + top-k from document collection, merged and sorted by distance). For image queries, at most `max_num_results` are returned. |

> **Note:** Provide exactly one of `query` or `image_base64` — not both.

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

---

#### Filter usage

Different filter keys are always combined with **AND**. When a filter value is a **list**, the matching logic depends on the field type:

| Field type | Example fields | List behavior | Operator used |
| ---------- | -------------- | ------------- | ------------- |
| **Array metadata** | `tags` | Matches if the stored array contains **at least one** of the filter values | `$contains` |
| **Scalar metadata** | `type`, `course`, `semester` | Matches if the stored value **equals any** of the filter values | `$eq` (OR) |

> **For Developer:** A placeholder for list fields parsed as `"and"` (all values must match) is available via the `list_filter_mode` parameter internally.

**Filter by tags** — returns results whose `tags` array contains `"biology"` or `"plants"`:

```bash
curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d '{
    "query": "lecture notes",
    "filter": { "tags": ["biology", "plants"] },
    "max_num_results": 5
  }'
```

**Filter by type** — available values: `"video"`, `"image"`, `"document"`. If not specified, all types are returned. Example returns only `video` or `document` results:

```bash
curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Newton first law",
    "filter": { "type": ["video", "document"] },
    "max_num_results": 5
  }'
```

> **Note:** Video-type results may appear even when `"video"` is not explicitly selected in the `type` filter, because relevant document summaries can be converted into video results during post-processing. These constructed results have `"original_type": "constructed_from_summary"` in their metadata to distinguish them from native video frame results.

**Filter for constructed summaries** — returns only video results that were constructed from document summaries:

```bash
curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Newton first law",
    "filter": { "original_type": "constructed_from_summary" },
    "max_num_results": 10
  }'
```

**Combined filter** — keys are ANDed together:

```bash
curl -X POST http://localhost:9990/v1/retrieval \
  -H "Content-Type: application/json" \
  -d '{
    "query": "lecture notes",
    "filter": { "course": "CS101", "tags": ["biology", "plants"] },
    "max_num_results": 3
  }'
```

Returns results where `course` equals `"CS101"` **AND** `tags` contains `"biology"` or `"plants"`.

---

#### Response

Results are sorted by `score` descending (highest relevance first). Each result includes:

- `id` — unique identifier of the indexed chunk/frame
- `distance` — cosine distance (lower = more similar)
- `meta` — metadata (see fields below)
- `score` — relevance score (0–100, higher = better)
- `reranker_score` — (documents only) raw cross-encoder score

The `filter` object accepts any metadata key present in the result's `meta` field (e.g. `type`, `tags`, `course`, `doc_filetype`, `original_type`). See [Filter usage](#filter-usage) for details on how scalar and array fields are matched.

```json
{
  "results": [
    {
      "id": "1329366430138679899",
      "distance": 0.2692107,
      "meta": {
        "chunk_text": "The scene then transitions to a whiteboard with handwritten notes about Newton's First Law of Motion. The notes explain that objects at rest tend to stay at rest unless an unbalanced force acts upon them, and objects in motion tend to continue moving in a straight",
        "chunk_index": 0,
        "type": "document",
        "doc_filetype": "text/plain"
      },
      "score": 97.9,
      "reranker_score": 3.841796875
    },
    {
      "id": "3024409473465277050",
      "distance": 0.2546569,
      "meta": {
        "file_path": "local://content-search/runs/6ee69571-ae4b-4ead-bff5-857b463a4b2a/raw/video/default/Newton_law.mp4",
        "type": "video",
        "original_type": "constructed_from_summary",
        "video_pin_second": 509.0,
        "summary_text": "The video is an animated educational piece about Newton's First Law of Motion, also known as the Law of Inertia. It features a stick figure character who appears to be teaching or explaining the concept."
      },
      "score": 74.53
    },
    {
      "id": "3671965433515452952",
      "distance": 0.7178304,
      "meta": {
        "file_path": "local://content-search/runs/6ee69571-ae4b-4ead-bff5-857b463a4b2a/raw/video/default/Newton_law.mp4",
        "type": "video",
        "video_pin_second": 394.0,
        "summary_text": "The video is a whiteboard animation that explains Newton's first law of motion, also known as the law of inertia."
      },
      "score": 28.22
    },
    {
      "id": "1670262849434704166",
      "distance": 0.7549856,
      "meta": {
        "file_path": "local://content-search/runs/fdc89165-a89a-4388-ace7-89bfc3a6b562/raw/image/default/test-newton.png",
        "type": "image"
      },
      "score": 24.5
    }
  ]
}
```

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

---

## Developer-Only APIs

> **Note:** The following endpoints are for testing and debugging purposes only. They are not part of the production API.

### DELETE /v1/dataprep/delete_by_ids

Delete specific entries by their IDs. Handles orphaned IDs (not tracked in id_maps) by attempting a fallback direct delete from both collections.

#### Request body

```json
{
  "ids": ["503415479151881641", "1234567890"]
}
```

- `ids` — list of string IDs to delete (IDs are stored as strings in ChromaDB)

#### Example

```bash
curl -X DELETE http://localhost:9990/v1/dataprep/delete_by_ids \
  -H "Content-Type: application/json" \
  -d '{"ids": ["id-1", "id-2"]}'
```

#### Response

```json
{
  "message": "Successfully deleted 2 entries. db returns: ...",
  "removed_ids": ["id-1", "id-2"]
}
```

> For orphaned ids, db returns empty

#### Error responses

| Code | Condition |
| --- | --- |
| `400` | `ids` is empty or not a list |
| `200` | No matching IDs found (still returns 200 with empty `removed_ids`) |
| `500` | Database error |

---

### POST /v1/retrieval/image

Perform image-based retrieval by uploading an image file directly (multipart form data). Avoids the manual base64 encoding step required by `/v1/retrieval`.

#### Form parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `image` | file | Yes | Image file (`.jpg`, `.png`, `.jpeg`) |
| `filter` | string | No | Metadata filter as JSON string (e.g., `{"course": "CS101"}`) |
| `max_num_results` | integer | No (default `10`) | Max results (1–16384) |

#### Example

```bash
curl -X POST http://localhost:9990/v1/retrieval/image \
  -F "image=@photo.jpg" \
  -F "max_num_results=5"
```

With filters:

```bash
curl -X POST http://localhost:9990/v1/retrieval/image \
  -F "image=@photo.jpg" \
  -F "filter={\"course\": \"CS101\", \"tags\": [\"biology\"]}" \
  -F "max_num_results=3"
```

#### Response

Same format as `/v1/retrieval`:

```json
{
  "results": [
    {
      "id": "abc123",
      "distance": 0.142,
      "score": 85.75,
      "meta": { "file_path": "local://...", "type": "image" }
    },
    ...
  ]
}
```

#### Error responses

| Code | Condition |
| --- | --- |
| `400` | `image` file is missing, invalid JSON in `filter`, or `max_num_results` out of range |
| `500` | Image processing or retrieval error |
