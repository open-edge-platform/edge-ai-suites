---
name: sc-qa
description: >
  Ask a natural-language question against indexed content via the Content Search
  RAG Q&A endpoint. Supports multi-turn conversation history (up to 3 turns by
  default), optional tag filtering to scope retrieval, and returns an answer with
  cited sources (document name, type, relevance score). Use when the user says
  "ask a question", "query the content", "what does the document say", "search
  the knowledge base", "multi-turn Q&A", "qa endpoint", "answer from
  documents", or "RAG question".
---

# SC QA

Ask a question against the indexed content using the Content Search RAG Q&A
endpoint with VLM-powered answer generation. **Agent: execute every command below
directly using your terminal tool and relay the output.** Endpoints use the base
URL `http://127.0.0.1:9011`.

**How it works:**
1. Content Search retrieves relevant chunks from indexed files (vector similarity via ChromaDB)
2. Chunks are sent to VLM service (port 8000) at `/v1/chat/completions`
3. VLM (Qwen3-VL-8B-Instruct) generates a grounded answer from the retrieved context
4. Response includes answer + cited sources (document name, type, relevance score)

**Two-phase operation:**
- **Phase 1 (vector retrieval)**: Always completes quickly (< 3 seconds)
- **Phase 2 (VLM generation)**: Takes 30-90 seconds; may fail with 503 if VLM is not ready

If VLM fails, the backend returns `code: 50003` with sources but no answer.

**Performance:** VLM answer generation can take 30-90 seconds for complex questions.

**Flutter Implementation:**
- `receiveTimeout`: 10 minutes (allows for long VLM processing)
- `maxHistoryTurns`: 3 (6 messages total: 3 user + 3 assistant)
- History snapshot is taken **before** appending the current question to avoid
  sending the in-flight message to the backend
- `UiKeepAliveInterceptor` keeps UI responsive during long VLM operations
- Errors are displayed as assistant messages with `isError: true`

Set `$BASE = "http://127.0.0.1:9011"` for all snippets.

---

## Preconditions

### Set corporate proxy (required for any outbound download; localhost API calls bypass it)

1. **Backend healthy** — probe first; if unreachable, use
   [`sc-doctor`](../sc-doctor/SKILL.md) / [`sc-up`](../sc-up/SKILL.md):
   ```powershell
   $BASE = "http://127.0.0.1:9011"
   # 200 = all services ready; 503 = degraded, body names the failing one
   try   { (Invoke-WebRequest -Uri "$BASE/api/v1/system/health" -UseBasicParsing).Content }
   catch { $_.ErrorDetails.Message }
   ```

2. **At least one file is indexed** — confirm with:
   ```powershell
   $r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list" -UseBasicParsing
   ($r.Content | ConvertFrom-Json).data.files | Select-Object file_name, status
   ```
   If no files are indexed, run [`sc-upload`](../sc-upload/SKILL.md) first.

---

## 1. Simple single-turn question

`POST /api/v1/object/qa`. The body has one required field (`question`); all
others are optional. See [`references/qa-request.md`](./references/qa-request.md)
for the full schema.

```powershell
$BASE = "http://127.0.0.1:9011"
$body = @{
    question = "What are the key topics covered in the uploaded lecture?"
} | ConvertTo-Json

$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/qa" `
     -Method POST `
     -ContentType "application/json" `
     -Body $body `
     -UseBasicParsing
$result = ($r.Content | ConvertFrom-Json)
Write-Host "Answer: $($result.data.answer)"
```

**Expected response shape:**
```json
{
  "code": 20000,
  "data": {
    "answer": "The lecture covers ...",
    "sources": [
      {
        "type": "document",
        "display_name": "lecture-notes.pdf",
        "score": 92.5
      }
    ]
  }
}
```

---

## 2. Multi-turn conversation (with history)

The backend accepts up to `QA_MAX_HISTORY_TURNS` (default: 3) prior turns.
History is an array of `{role, content}` objects — include the last N completed
pairs **before** appending the current question:

```powershell
$BASE = "http://127.0.0.1:9011"

# Build history from previous turns (user + assistant alternating)
$history = @(
    @{ role = "user";      content = "What is a vector space?" },
    @{ role = "assistant"; content = "A vector space is a set of vectors..." }
)

$body = @{
    question = "Can you give me a concrete example with 2D vectors?"
    history  = $history
} | ConvertTo-Json -Depth 5

$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/qa" `
     -Method POST `
     -ContentType "application/json" `
     -Body $body `
     -UseBasicParsing
($r.Content | ConvertFrom-Json).data.answer
```

> **History ordering rule:** History must contain completed turns only (no
> in-flight user message). 
>
> **Flutter implementation detail:** The `QaNotifier._buildHistory()` method
> takes a snapshot of `state.messages` **before** appending the current question.
> This prevents sending a mid-conversation state to the backend. The snapshot
> captures the last `maxHistoryTurns * 2` (6) messages, filters out error messages,
> and converts them to `{role, content}` pairs.

---

## 3. Scope retrieval with tag filters

Use the `filter` field to restrict which indexed files are searched.
Tags must have been set at upload time (see [`sc-upload`](../sc-upload/SKILL.md)).

```powershell
# First, see available tags
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/tags" -UseBasicParsing
($r.Content | ConvertFrom-Json).data

# Then ask with a tag filter
$body = @{
    question = "Summarize the key equations"
    filter   = @{ tags = @("mathematics","week1") }
} | ConvertTo-Json -Depth 5

$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/qa" `
     -Method POST -ContentType "application/json" `
     -Body $body -UseBasicParsing
($r.Content | ConvertFrom-Json).data.answer
```

---

## 4. Display sources

Sources returned alongside the answer carry relevance metadata:

```powershell
$result = ($r.Content | ConvertFrom-Json).data
Write-Host "Answer:`n$($result.answer)`n"
Write-Host "Sources:"
$result.sources | ForEach-Object {
    $score = if ($_.score -le 1) { [math]::Round($_.score * 100, 1) } else { $_.score }
    Write-Host "  [$($_.type)] $($_.display_name) — score: ${score}%"
}
```

> **Score normalisation:** the backend may return scores as `0.0–1.0` floats
> or as `0–100` percentages. Multiply by 100 if the value is ≤ 1, as done in
> `QaSource.fromJson()` in the Flutter app.

---

## 5. Understanding Partial Success (Code 50003)

When the Content Search backend returns `code: 50003` with sources but no answer,
it means:

1. ✅ **Vector retrieval succeeded** — relevant chunks were found in ChromaDB
2. ❌ **VLM answer generation failed** — VLM endpoint returned 503 Service Unavailable

**Example response:**
```json
{
  "code": 50003,
  "data": {
    "sources": [
      {"file_name": "doc.pdf", "score": 99.12, "type": "document"},
      ...
    ]
  },
  "message": "Server error '503 Service Unavailable' for url 'http://127.0.0.1:8000/v1/chat/completions'"
}
```

**Why this happens:**
- VLM model may still be loading (first 2-3 minutes after startup)
- VLM service crashed or is overloaded
- Main backend `/v1/chat/completions` endpoint is not responding

**How to fix:**
```powershell
# Check if VLM is ready
$health = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing).Content | ConvertFrom-Json
$health.hub.text_gen.state  # Should be "ready"

# If not ready or service crashed, restart main backend
# Close the backend window and run:
.\utils\flutter\start.ps1
```

**Flutter behavior:**
- The Flutter app catches this error and displays it as an assistant message with `isError: true`
- Sources are still shown to the user even though answer generation failed
- User can retry the question once VLM is healthy

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `answer` is empty | No relevant content found | Check that the right files are indexed; verify tags filter isn't too narrow |
| `code: 40000` / 400 Bad Request | Missing or malformed `question` field | Ensure `question` is a non-empty string |
| `code: 50003` + sources returned | VLM endpoint 503 error (retrieval OK, generation failed) | Check main backend logs at `smart-classroom/logs`; VLM may be loading or crashed; restart main backend |
| Very slow response (>30 s) | VLM generation is slow | Normal for complex questions; wait up to 10 min (Flutter `receiveTimeout`) |
| Sources are from wrong files | Tag filter not set | Pass `filter.tags` to scope retrieval |
| History causes hallucination | Too many stale turns | Limit history to last 3 turns (matches `AppConfig.maxHistoryTurns`) |
| 500 Internal Server Error | VLM service error | Check main backend logs (port 8000); verify VLM is healthy |
| 503 Service Unavailable from VLM | VLM `/v1/chat/completions` not responding | VLM model may not be loaded; check main backend health shows `text_gen: ready`; restart if needed |
| Connection timeout | VLM not responding | Check main backend health; VLM may need restart |

---

## Output

Report: **question sent** → **answer text** → **sources list** (name + type +
score). For multi-turn, include how many history turns were included.
