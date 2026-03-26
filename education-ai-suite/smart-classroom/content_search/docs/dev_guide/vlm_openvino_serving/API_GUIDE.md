# VLM OpenVINO Serving — API Guide

Base URL: `http://<host>:9900`

---

## Table of Contents

1. [Health Check](#health-check)
2. [Chat Completions](#chat-completions)
   - [Request Body](#request-body)
   - [Message Content Types](#message-content-types)
   - [Example Requests](#example-requests)
   - [Response](#response)
3. [Behavior Notes](#behavior-notes)
4. [Error Responses](#error-responses)

---

## Health Check

### `GET /health`

Returns model readiness.

**Request**

```bash
curl http://localhost:9900/health
```

**Healthy response**

```json
{ "status": "healthy" }
```

**Not ready response**

```json
{ "status": "model not ready" }
```

- HTTP `200`: model ready
- HTTP `503`: model not ready

---

## Chat Completions

### `POST /v1/chat/completions`

OpenAI-compatible chat-completions style endpoint for text and image understanding.

### Request Body

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `messages` | array | Yes | — | Chat history (`role` + `content`) |
| `model` | string | No | `null` | Ignored by runtime selection; runtime model comes from server config |
| `max_completion_tokens` | integer | No | env `VLM_MAX_COMPLETION_TOKENS` (or model default) | Max generated tokens |
| `temperature` | number | No | model/runtime default | Sampling temperature |
| `top_p` | number | No | model/runtime default | Nucleus sampling parameter |
| `top_k` | integer | No | model/runtime default | Top-k sampling parameter |
| `do_sample` | boolean | No | model/runtime default | Sampling enable flag |
| `repetition_penalty` | number | No | model/runtime default | Repetition penalty |
| `presence_penalty` | number | No | model/runtime default | Presence penalty |
| `frequency_penalty` | number | No | model/runtime default | Frequency penalty |
| `seed` | integer | No | env `SEED` | Random seed for reproducibility |
| `stream` | boolean | No | `false` | Accepted by schema, but current implementation returns non-streaming response |

### Message Content Types

Each `messages[i]` item supports:

- `content` as plain string
- `content` as an array containing text/image parts:
  - Text part:
    ```json
    { "type": "text", "text": "Describe this image." }
    ```
  - Image part:
    ```json
    { "type": "image_url", "image_url": { "url": "https://... or data:image/...;base64,..." } }
    ```

### Example Requests

**Text-only**

```bash
curl -X POST http://localhost:9900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      { "role": "user", "content": "Summarize the key events in one paragraph." }
    ],
    "max_completion_tokens": 300,
    "temperature": 0.1
  }'
```

**Text + image URL**

```bash
curl -X POST http://localhost:9900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "Describe what is happening in this image." },
          { "type": "image_url", "image_url": { "url": "https://example.com/image.jpg" } }
        ]
      }
    ],
    "max_completion_tokens": 400
  }'
```

**Text + base64 image**

```bash
curl -X POST http://localhost:9900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "Describe this image." },
          { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,<BASE64_DATA>" } }
        ]
      }
    ],
    "max_completion_tokens": 200
  }'
```

### Response

```json
{
  "id": "9bd80537-4fa8-4f6d-b5f4-cc991e415335",
  "object": "chat.completion",
  "created": 1770000000,
  "model": "Qwen/Qwen2.5-VL-3B-Instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The image shows ..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": null
}
```

---

## Behavior Notes

- The service extracts prompt/images primarily from the **last `user` message** in `messages`.
- When no prompt text is found, the endpoint returns HTTP `400` with `{"error": "Prompt is required"}`.
- The endpoint currently responds as a full JSON completion (non-streaming), even if `stream=true` is provided.
- `messages` can include multi-turn context; text-only and vision-text requests are both supported.

---

## Error Responses

| Code | Meaning |
|---|---|
| `400` | Invalid request content (for example, missing prompt) |
| `422` | Request body validation error (for example, malformed `messages`) |
| `500` | Internal model/inference/server error |
| `503` | Model not ready (`GET /health` only) |

Error payloads are JSON and usually include an `error` field, for example:

```json
{ "error": "Prompt is required" }
```
