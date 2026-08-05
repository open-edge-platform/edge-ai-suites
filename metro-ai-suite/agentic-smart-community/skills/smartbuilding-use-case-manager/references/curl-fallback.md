# Direct `/v1/tasks` Curl Flow (fallback when MCP is unavailable)

Use this only when the Smart Building MCP server is unavailable and the user
only asked for a video-summary task (list / show / create / edit / delete).
Do **not** claim a Smart Building use case is registered unless
`smartbuilding_use_case_register` succeeds — this flow manages raw VLM tasks
only.

Authoring rules (anchors, placeholders, `KEY: value` output contract, lint
checklist) are the same as in `SKILL.md`; draft the four sections from the
template there, translated into the user's language.

## Prerequisites

```bash
: "${VIDEO_SUMMARY_BASE_URL:=http://localhost:8192}"
export VIDEO_SUMMARY_BASE_URL
curl -fsS "$VIDEO_SUMMARY_BASE_URL/v1/health" | jq .
```

## Task naming on the curl flow

- `task_name` must match `^[a-z][a-z0-9_]{1,63}$`.
- Append the `_zh` / `_en` suffix to `task_name` according to the prompt
  language (e.g. `<task_name>_zh`). This suffix convention applies ONLY to
  direct `/v1/tasks` calls — in the MCP flow the task name stays
  `<use_case>_monitor` regardless of prompt language.
- Never shadow, modify, or delete built-in tasks reported by `/v1/tasks`;
  inspect before overwriting or deleting.

## Recipes

```bash
# List all tasks (built-in + dynamic)
curl -sS "$VIDEO_SUMMARY_BASE_URL/v1/tasks" | jq .

# Inspect one task — returns `{name, source, description, content}` where
# `content` is a single round-trip-safe string with all four anchor sections
# concatenated. Copy it, edit, and re-submit as `content.text`.
curl -sS "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" | jq .

# Delete a dynamic task (built-ins are 403)
curl -sS -X DELETE "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" -w "%{http_code}\n"
```

### Register full-mode (the primary workflow)

Write the body to a file so shell-quoting doesn't interfere. `content.text` is
the four anchor sections concatenated with literal `\n` between lines (see the
template in `SKILL.md`).

```bash
cat > /tmp/body.json <<'JSON'
{
  "task_name": "<task_name>",
  "mode": "full",
  "description": "<natural language use case description>",
  "content": {
    "text": "<<< the 4-anchor content string, with literal \\n between lines >>>"
  }
}
JSON

curl -sS -X POST "$VIDEO_SUMMARY_BASE_URL/v1/tasks" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/body.json | jq .
```

### PATCH variants (rename / replace content / edit description)

```bash
# Rename only
curl -sS -X PATCH "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" \
  -H 'Content-Type: application/json' \
  -d '{"new_task_name": "<new>"}' | jq .

# Replace all four sections (same body shape as register, plus "mode":"full")
curl -sS -X PATCH "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/body.json | jq .

# Description only
curl -sS -X PATCH "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" \
  -H 'Content-Type: application/json' \
  -d '{"description": "<new>"}' | jq .
```

### Autogen mode (fallback, lower quality)

Use only if drafting a full prompt is not feasible. Quality depends on the
model the service is configured with via `LLM_MODEL_NAME` / `LLM_BASE_URL`.

```bash
curl -sS -X POST "$VIDEO_SUMMARY_BASE_URL/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"task_name":"<name>","mode":"autogen","description":"<natural language use case>"}' | jq .
```

## Error Handling

| Status | Code | Fix |
|---|---|---|
| 201 | (success) | Show the four sections to the user |
| 422 | `missing_anchors` | Read `missing` + `reference_template`; add the anchors, retry |
| 422 | `missing_placeholders` | Section names a required `{foo}`; reply with `section` + `missing` |
| 422 | `autogen_empty_output` | Service LLM returned nothing; retry once, else switch to `mode=full` |
| 400 | `parse_error` | Content malformed (unbalanced `'''`, stray token); compare with `reference_template` |
| 400 | `duplicate_anchor` | Same anchor twice; keep one |
| 400 | `invalid_name` | `task_name` doesn't match `^[a-z][a-z0-9_]{1,63}$` |
| 400 | `banned_token` | Contains triple-backtick fence or `<<<`; remove |
| 400 | `invalid_url` | Non-HTTPS or private-network URL |
| 409 | `builtin_conflict` | Name matches a built-in; pick a different name |
| 409 | `already_registered` | Name used by another dynamic task; pick different or PATCH |
| 403 | `builtin_immutable` | Tried to PATCH / DELETE a built-in; register a new one instead |
| 404 | `not_found` | Typo or never registered; list first |

Retry budget: ≤ 2 attempts on 4xx. On the third failure, surface the server's
`detail` + `reference_template` to the user and ask for guidance.

## Notes

- **Persistence**: dynamic tasks live under the service's
  `VIDEO_SUMMARY_CACHE` dir (default `~/.cache/.multilevel-video-understanding`
  on the host). They survive container restarts.
- **Round-trip editing**: the `content` field returned by GET is ready to
  POST/PATCH back — no reformatting needed.
- **URL content**: `content.url` (HTTPS only, ≤ 256 KB, public hosts) is an
  alternative to `content.text` for loading the four-section string from a
  remote file.
