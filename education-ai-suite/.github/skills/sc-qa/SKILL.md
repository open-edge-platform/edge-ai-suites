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
endpoint. **Agent: execute every command below directly using your terminal tool
and relay the output.** Endpoints use the base URL `http://127.0.0.1:9011`.

Set `$BASE = "http://127.0.0.1:9011"` for all snippets.

---

## Preconditions

### Set corporate proxy (required for any outbound download; localhost API calls bypass it)

1. **Backend healthy** — probe first; if unreachable, use
   [`sc-doctor`](../sc-doctor/SKILL.md) / [`sc-up`](../sc-up/SKILL.md):
   ```powershell
   $BASE = "http://127.0.0.1:9011"
   Invoke-WebRequest -Uri "$BASE/api/v1/system/health" -UseBasicParsing |
       Select-Object -ExpandProperty Content
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

> **History ordering rule:** history must contain completed turns only (no
> in-flight user message). The Flutter `QaNotifier` captures a snapshot of
> `state.messages` *before* appending the current question to avoid sending
> a mid-conversation state to the backend.

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

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `answer` is empty | No relevant content found | Check that the right files are indexed; verify tags filter isn't too narrow |
| `code: 40000` / 400 Bad Request | Missing or malformed `question` field | Ensure `question` is a non-empty string |
| Very slow response (>30 s) | LLM generation is slow | Normal for large context; wait up to the `receiveTimeout` (10 min in the Flutter app) |
| Sources are from wrong files | Tag filter not set | Pass `filter.tags` to scope retrieval |
| History causes hallucination | Too many stale turns | Limit history to last 3 turns (matches `AppConfig.maxHistoryTurns`) |
| 500 Internal Server Error | Backend LLM error | Check backend logs via `sc-doctor`; verify LLM endpoint config |

---

## Output

Report: **question sent** → **answer text** → **sources list** (name + type +
score). For multi-turn, include how many history turns were included.
