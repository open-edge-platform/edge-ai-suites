# Inspecting an Existing Use Case's Schema

Read this only when refining / re-registering an **existing** use case. For a
NEW use case there is nothing to read — the Final Schema is what the Q1/Q2
answers decided (see `SKILL.md`).

Schema is owned **per use case** at
`use_case_dict.<uc>.schema.video_summary_tasks.extensions` — there is **no**
global `schema:` block, so a `.schema.video_summary_tasks...` query at the top
level always returns empty.

Inspect via the server's booted config (`dirname(--config)` of the MCP server):

```bash
if [[ -f config.yaml ]]; then
  CFG=config.yaml
else
  CFG=config.yaml.example
fi

yq '.use_case_dict.<use_case>.schema.video_summary_tasks.extensions // []' "$CFG"
```

Notes:

- `config.yaml.example` is the fallback when the server booted from the
  example (some environments have no `config.yaml`; in that case
  `persist=true` writes back into `config.yaml.example` itself).
- The Smart Building runtime is **not** a JSON parser for summary output — it
  scans plain text for one `field_name: value` line per field. Field names in
  the Final Schema are consumed downstream by `parseSummaryFields`; the VLM
  must emit those exact field names or extraction/rules silently miss.
- When rebuilding a prompt from an existing schema:
  - `required=true` fields: must appear as one line each in the output contract.
  - `required=false` fields: emit only when detectable in the clip.
  - Keep the original lowercase field names (no renaming/translation of keys).
