# Q&A Request — Schema Reference

Full reference for `POST /api/v1/object/qa`.

## Request body

```json
{
  "question": "What is the main topic of the lecture?",
  "history": [
    { "role": "user",      "content": "Prior user message" },
    { "role": "assistant", "content": "Prior assistant reply" }
  ],
  "filter": {
    "tags": ["math,week1"]
  }
}
```

## Field reference

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | `string` | **Yes** | The natural-language question to answer. Must be non-empty. |
| `history` | `array<{role, content}>` | No | Prior conversation turns. `role` must be `"user"` or `"assistant"`. Alternates user/assistant. Max 3 turns (6 messages) by default (`QA_MAX_HISTORY_TURNS` backend env var). |
| `filter` | `object` | No | Retrieval scope filters. Currently supports `tags`. |
| `filter.tags` | `array<string>` | No | Tag list. Only chunks from files tagged with at least one of the specified tags are retrieved (backend builds `$contains` clauses for list-valued `tags`). |

## Response body

```json
{
  "code": 20000,
  "data": {
    "answer": "The lecture focuses on ...",
    "sources": [
      {
        "type": "document",
        "display_name": "lecture-notes.pdf",
        "file_name": "lecture-notes.pdf",
        "score": 0.925,
        "timestamp": null
      },
      {
        "type": "video",
        "display_name": "intro-video.mp4",
        "file_name": "intro-video.mp4",
        "score": 0.78,
        "timestamp": "01:23"
      }
    ]
  }
}
```

## Source field reference

| Field | Type | Description |
|---|---|---|
| `type` | `string` | `"document"` \| `"video"` \| `"image"` |
| `display_name` | `string` | Human-readable file name or title for display |
| `file_name` | `string` | Raw filename fallback |
| `score` | `number` | Relevance score. May be `0–1` float or `0–100`. Multiply by 100 if ≤ 1 (Flutter `QaSource.fromJson` does this automatically). |
| `timestamp` | `string \| null` | For video sources: formatted timestamp (e.g. `"01:23"`). `null` for documents. |

## Flutter mapping

The Flutter `QaRequest` model (`lib/models/qa_models.dart`) maps directly:

```dart
QaRequest(
  question: "What is the main topic?",
  history: [
    QaHistoryMessage(role: "user",      content: "Earlier question"),
    QaHistoryMessage(role: "assistant", content: "Earlier answer"),
  ],
  filter: {"tags": "math,week1"},
)
```

`QaNotifier` caps history at `AppConfig.maxHistoryTurns * 2` messages (default: 6)
and snapshots the history *before* appending the current user message.
