# API

Base URL (default): `http://127.0.0.1:8020`

## Health

### `GET /health`

Returns service liveness.

Response:

```json
{"status":"ok"}
```

## Service Metadata

### `GET /api/v1/model-info`

Returns the active runtime model and retrieval configuration summary used by the service.

Typical response fields include:

- `llm_device`
- `llm_weight_format`
- `embedding_device`
- `top_k`
- pipeline statistics returned by the shared RAG pipeline

### `GET /api/v1/performance`

Returns runtime performance metrics collected for answer generation.

Response includes:

- `latency.retrieval.last_ms`
- `latency.llm.last_ms`
- `latency.llm.ttft_ms` (time to first token)
- `latency.llm.tokens_per_sec`
- `latency.llm.total_tokens`

## Context Ingestion

### `POST /api/v1/context`

Request body:

```json
{
  "text": "Alfonso mangoes are in Produce near the tropical fruit display.",
  "source": "store-manual",
  "metadata": {
    "department": "produce"
  }
}
```

Response:

```json
{
  "chunks_added": 1,
  "source": "store-manual"
}
```

### `POST /api/v1/context/file`

Upload a UTF-8 `.txt` or `.md` file using multipart form-data with the `file` field.

Validation rules:

- only `.txt` and `.md` files are accepted
- file size is limited to 10 MB
- content must decode as UTF-8
- ingest is rejected if token count exceeds `RAG_MAX_INGEST_TOKENS` (default `25000`)

### `GET /api/v1/context/stats`

Returns collection metadata and the current stored document count.

### `DELETE /api/v1/context`

Clears the active Chroma collection.

Response:

```json
{
  "status": "cleared"
}
```

## Kiosk Query API

### `POST /api/v1/query`

Request body:

```json
{
  "transcription": "Where can I find Alfonso mangoes?",
  "context_text": "Customer is standing near produce.",
  "top_k": 3,
  "include_sources": true,
  "history": [
    {"role": "user", "content": "I am in produce."},
    {"role": "assistant", "content": "What are you looking for?"}
  ]
}
```

Request fields:

- `transcription`: required user question text
- `context_text`: optional runtime context supplied by kiosk-core
- `top_k`: optional retrieval override, `1` to `20`
- `include_sources`: when `true`, appends a final sources payload before `[DONE]`
- `history`: optional prior conversation turns, oldest-first; each turn must be `{role, content}` with `role` in `user|assistant`

Response type: `text/event-stream`

Events:

- `data: {"token":"..."}` for streamed answer fragments
- optional final sources payload when `include_sources=true`
- `data: [DONE]` sentinel

Notes:

- `top_k` is optional; if omitted, the service default from `config.yaml` is used.
- `context_text` is optional runtime context from kiosk-core, such as the user's location or active screen context.
- `history` is trimmed by the pipeline when the configured context budget is tight.
- when `include_sources=true`, the final payload has the form below:

```json
{
  "event": "sources",
  "sources": [
    {
      "source": "store-manual",
      "score": 0.12,
      "metadata": {"department": "produce"},
      "content": "Alfonso mangoes are in Produce near the tropical fruit display."
    }
  ],
  "answer": "You can find Alfonso mangoes in Produce near the tropical fruit display."
}
```

## OpenAI-Compatible Chat

### `POST /v1/chat/completions`

Implements an OpenAI-compatible chat completion surface over the same RAG pipeline.

Behavior details:

- the final `user` message becomes the active question
- the final `system` message, if present, is used as the system prompt override
- earlier `user` and `assistant` messages become conversation history
- message content can be either a string or an array of content parts; only `type: "text"` parts are used from structured content arrays

Non-stream example:

```json
{
  "model": "smart-kiosk-rag",
  "messages": [
    {"role": "system", "content": "Answer briefly."},
    {"role": "user", "content": "Where is the bakery?"}
  ],
  "stream": false,
  "temperature": 0.0,
  "max_tokens": 192
}
```

Streaming example uses the same payload with `"stream": true` and returns standard SSE `data:` events ending with `[DONE]`.

Non-stream response shape:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "smart-kiosk-rag",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "The bakery is near the front entrance."},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "total_tokens": null
  }
}
```
