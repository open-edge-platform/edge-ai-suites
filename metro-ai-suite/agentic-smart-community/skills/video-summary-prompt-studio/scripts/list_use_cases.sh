#!/usr/bin/env bash
# List registered use-case keys from the MCP server's booted config.
#
# Usage: list_use_cases.sh [config-file]
#
# CFG must be the file the MCP server booted from (dirname of its --config
# argument) — persist=true writes back to THAT file, which is not necessarily
# the config.yaml in your CWD.
set -euo pipefail

if [[ $# -ge 1 ]]; then
  CFG="$1"
elif [[ -f config.yaml ]]; then
  CFG=config.yaml
else
  CFG=config.yaml.example
fi

if command -v yq >/dev/null 2>&1; then
  yq '.use_case_dict | keys' "$CFG"
else
  # yq-free fallback: print the 2-space-indented keys directly under
  # `use_case_dict:` (use case ids), stopping at the next top-level key.
  awk '
    /^use_case_dict:/ { inblk=1; next }
    inblk && /^[^[:space:]#]/ { inblk=0 }
    inblk && /^  [A-Za-z0-9_]+:/ { sub(/:.*/, ""); gsub(/ /, ""); print }
  ' "$CFG"
fi
