# Inspecting an Existing Use Case's Schema

Read this only when refining / re-registering an **existing** use case. For a
NEW use case there is nothing to read — the Final Schema is what the Q1/Q2
answers decided (see `SKILL.md`).

Schema is owned **per use case** at
`use_case_dict.<uc>.schema.video_summary_tasks.extensions` — there is **no**
global `schema:` block, so a `.schema.video_summary_tasks...` query at the top
level always returns empty.

Inspect via the server's booted config — the `config.yaml` in the server's
data dir, NOT any config file in your CWD:

```bash
CFG="${SMARTBUILDING_DATA_DIR:-$HOME/.mcp-smartbuilding}/config.yaml"

yq '.use_case_dict.<use_case>.schema.video_summary_tasks.extensions // []' "$CFG"
```

Notes:

- The active config is the one the MCP server booted from (its `--config`
  argument): `<data_dir>/config.yaml`, where `<data_dir>` is
  `$SMARTBUILDING_DATA_DIR` or `~/.mcp-smartbuilding` by default.
  `persist=true` writes back into THAT file. A `config.yaml` /
  `config.yaml.example` in your CWD is not the live config. When the MCP
  server is reachable, prefer `smartbuilding_use_case_register action=list`
  over reading the file — it reflects the live in-memory `use_case_dict`.
- The Smart Building runtime is **not** a JSON parser for summary output — it
  scans plain text for one `field_name: value` line per field. Field names in
  the Final Schema are consumed downstream by `parseSummaryFields`; the VLM
  must emit those exact field names or extraction/rules silently miss.
- When rebuilding a prompt from an existing schema:
  - `required=true` fields: must appear as one line each in the output contract.
  - `required=false` fields: emit only when detectable in the clip.
  - Keep the original lowercase field names (no renaming/translation of keys).
