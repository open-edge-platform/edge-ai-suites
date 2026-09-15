#!/usr/bin/env bash
#
# One-shot install for the smart-community-alerts OpenClaw framework adapter — demo flavour.
#
# The plugin-only half (build SDK, install deps, unlink/link, validate, restart gateway)
# lives in the example's own clean script and is reused here, not duplicated:
#   packages/framework-adapter-sdk/examples/openclaw/scripts/install_as_openclaw_plugin.sh
#
# This script adds only the demo-specific runtime on top of it:
#
#   1. plugin prepare        (delegated: build SDK, plugin deps, unlink)
#   2. register the plugin entry + the demo's alert routes        (per-monitor merge)
#   3. merge the demo agents into agents.list[]                   (merge-by-id, non-destructive)
#   4. install the repo's skills into ~/.openclaw/skills/         (OpenClaw discovers them natively)
#   5. copy the bundled agent personas into ~/.openclaw/agents/   (cp -n: never clobbers)
#   6. plugin finalize       (delegated: symlink, config validate, gateway restart)
#   7. wake up the demo agents so their sessions exist            (openclaw agent -m hi)
#
# Steps 2–5 run between `prepare` and `finalize` on purpose: OpenClaw enforces the
# plugin's required-field schema the instant it is discovered (symlinked), so a symlink
# without config makes the whole config invalid and blocks `openclaw config patch`.
# `prepare` leaves the plugin unlinked precisely so this window is patchable.
#
# Fully automated & idempotent: safe to re-run — and self-heals a half-finished run.
# The persona copy, plugin config, and agents you added yourself are never clobbered.
#
# Env overrides:
#   OPENCLAW_HOME   target home                       (default: ~/.openclaw)
#   MCP_URL         Smart Community MCP endpoint         (default: http://localhost:3100/mcp)
#   AGENT_MODEL     model for new demo agents          (default: agents.defaults.model.primary)
#   SKIP_RESTART=1  skip the gateway restart (step 6)
#   SKIP_WAKEUP=1   skip the agent wakeup   (step 7)
set -euo pipefail

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
HERE="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"      # demo/openclaw-adapter
REPO_ROOT="$(cd "$HERE/../.." && pwd)"                # agentic-smart-community
SDK_DIR="$REPO_ROOT/packages/framework-adapter-sdk"
PLUGIN_DIR="$SDK_DIR/examples/openclaw"
PLUGIN_INSTALL_SH="$PLUGIN_DIR/scripts/install_as_openclaw_plugin.sh"
PERSONA_DIR="$HERE/agents"
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
# Keep it out of the child environment: the `openclaw` CLI reads OPENCLAW_HOME as a
# $HOME override and would then look for $OPENCLAW_HOME/.openclaw/openclaw.json.
# Child scripts get the value explicitly, via --openclaw-home.
export -n OPENCLAW_HOME
PLUGIN_ID="smart-community-alerts"
MCP_URL_EXPLICIT=false
[[ -n "${MCP_URL+x}" ]] && MCP_URL_EXPLICIT=true
MCP_URL="${MCP_URL:-http://localhost:3100/mcp}"
AGENT_MODEL="${AGENT_MODEL:-}"

# Demo agents (id order matters: `main` first — it is OpenClaw's default agent).
# The 3 persona agents below are the ones with bundled workspaces under agents/.
PERSONA_AGENTS=(fridge-agent child-safety-agent elder-wakeup-agent)

command -v openclaw >/dev/null 2>&1 || { echo "ERROR: 'openclaw' CLI not found on PATH." >&2; exit 1; }
command -v npm      >/dev/null 2>&1 || { echo "ERROR: 'npm' not found on PATH."      >&2; exit 1; }
command -v jq       >/dev/null 2>&1 || { echo "ERROR: 'jq' not found on PATH."       >&2; exit 1; }
[[ -f "$PLUGIN_INSTALL_SH" ]] || { echo "ERROR: plugin install script not found: $PLUGIN_INSTALL_SH" >&2; exit 1; }
[[ -d "$PERSONA_DIR" ]] || { echo "ERROR: demo agent personas not found: $PERSONA_DIR" >&2; exit 1; }

# The MCP server runs in containers, so users normally do not install the root
# npm workspace. The plugin SDK still needs its TypeScript dev dependency once.
if [[ ! -x "$SDK_DIR/node_modules/.bin/tsc" && ! -x "$REPO_ROOT/node_modules/.bin/tsc" ]]; then
  echo "==> SDK build dependencies not found; installing workspace dev dependencies"
  npm --prefix "$REPO_ROOT" ci --include=dev
fi


if [[ -z "$AGENT_MODEL" ]]; then
  configured_model="$(openclaw config get agents.defaults.model.primary --json 2>/dev/null || true)"
  AGENT_MODEL="$(jq -r 'if type == "string" then . else empty end' <<<"$configured_model")"
fi
[[ -n "$AGENT_MODEL" ]] || {
  echo "ERROR: No default OpenClaw model is configured. Configure a provider first or set AGENT_MODEL." >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Step 1 — plugin prepare (clean script): build SDK, install plugin deps, and
# leave the plugin UNLINKED so the config patches below are allowed to run.
# ---------------------------------------------------------------------------
echo "==> Preparing the OpenClaw plugin (build + deps + unlink)"
bash "$PLUGIN_INSTALL_SH" prepare --openclaw-home "$OPENCLAW_HOME" --plugin-id "$PLUGIN_ID"

# The demo's alert routes: monitor id -> where its alerts are delivered.
DEMO_MONITORS="$(jq -n '{
  cam_child: {
    alerts: [ { agentId: "child-safety-agent", sessionKey: "agent:child-safety-agent:cam_child", deliver: false } ]
  },
  cam_elder_bedroom: {
    alerts: [ { agentId: "elder-wakeup-agent", sessionKey: "agent:elder-wakeup-agent:cam_elder_bedroom", deliver: false } ]
  }
}')"

# ---------------------------------------------------------------------------
# Step 2 — register the plugin entry, then add the demo's monitor routes.
# `openclaw config patch` merges objects recursively and validates before writing,
# so this never disturbs the other plugins (minimax/tavily/…).
#
# Routes are merged PER MONITOR, not per entry: an entry that already exists (say
# with a hand-added cam_test) must not swallow the demo's own routes, and the demo's
# routes must not clobber yours. Each monitor id is written only when that exact
# key is absent, so re-runs and hand edits both survive.
# ---------------------------------------------------------------------------
echo "==> Registering plugin entry in openclaw.json"
if openclaw config get "plugins.entries.$PLUGIN_ID" --json >/dev/null 2>&1; then
  if [[ "$MCP_URL_EXPLICIT" == "true" ]]; then
    patch_file="$(mktemp)"
    jq -n --arg id "$PLUGIN_ID" --arg url "$MCP_URL" \
      '{ plugins: { entries: { ($id): { config: { mcpServer: { url: $url } } } } } }' > "$patch_file"
    openclaw config patch --file "$patch_file"
    rm -f "$patch_file"
    echo "    - updated mcpServer.url=$MCP_URL"
  else
    echo "    - entry already present (mcpServer left as-is)"
  fi
else
  patch_file="$(mktemp)"
  jq -n --arg id "$PLUGIN_ID" --arg url "$MCP_URL" \
    '{ plugins: { entries: { ($id): { enabled: true, config: { mcpServer: { url: $url }, monitors: {} } } } } }' > "$patch_file"
  openclaw config patch --file "$patch_file"
  rm -f "$patch_file"
  echo "    - registered $PLUGIN_ID (mcpServer=$MCP_URL)"
fi

echo "==> Adding the demo's alert routes (per-monitor merge)"
while read -r monitor_id; do
  if openclaw config get "plugins.entries.$PLUGIN_ID.config.monitors.$monitor_id" --json >/dev/null 2>&1; then
    echo "    - $monitor_id already routed — left as-is"
    continue
  fi
  patch_file="$(mktemp)"
  jq -n --arg id "$PLUGIN_ID" --arg mon "$monitor_id" \
    --argjson route "$(jq -c --arg mon "$monitor_id" '.[$mon]' <<<"$DEMO_MONITORS")" \
    '{ plugins: { entries: { ($id): { config: { monitors: { ($mon): $route } } } } } }' > "$patch_file"
  openclaw config patch --file "$patch_file"
  rm -f "$patch_file"
  echo "    - routed $monitor_id -> $(jq -r --arg mon "$monitor_id" '.[$mon].alerts[0].sessionKey' <<<"$DEMO_MONITORS")"
done < <(jq -r 'keys[]' <<<"$DEMO_MONITORS")

# ---------------------------------------------------------------------------
# Step 3 — merge the demo agents into agents.list[] (merge-by-id, non-destructive).
# `config patch` replaces arrays, so we read the current list, append only the
# agents whose id is missing, then write the merged array back. This also folds
# the implicit default `main` into the explicit list on a fresh install.
# ---------------------------------------------------------------------------
echo "==> Merging demo agents into agents.list"
existing_list="$(openclaw config get agents.list --json 2>/dev/null || true)"
echo "$existing_list" | jq -e 'type == "array"' >/dev/null 2>&1 || existing_list='[]'

desired_agents="$(cat <<EOF
[
  { "id": "main",               "name": "main",               "workspace": "\${HOME}/.openclaw/workspace",                       "agentDir": "\${HOME}/.openclaw/agents/main/agent",               "model": "$AGENT_MODEL", "thinkingDefault": "off" },
  { "id": "fridge-agent",       "name": "fridge-agent",       "workspace": "\${HOME}/.openclaw/agents/fridge-agent/workspace",       "agentDir": "\${HOME}/.openclaw/agents/fridge-agent/agent",       "model": "$AGENT_MODEL", "thinkingDefault": "off" },
  { "id": "child-safety-agent", "name": "child-safety-agent", "workspace": "\${HOME}/.openclaw/agents/child-safety-agent/workspace", "agentDir": "\${HOME}/.openclaw/agents/child-safety-agent/agent", "model": "$AGENT_MODEL", "thinkingDefault": "off" },
  { "id": "elder-wakeup-agent", "name": "elder-wakeup-agent", "workspace": "\${HOME}/.openclaw/agents/elder-wakeup-agent/workspace", "agentDir": "\${HOME}/.openclaw/agents/elder-wakeup-agent/agent", "model": "$AGENT_MODEL", "thinkingDefault": "off" }
]
EOF
)"

merged_list="$(jq -n \
  --argjson existing "$existing_list" \
  --argjson desired "$desired_agents" '
    ($existing | map(.id)) as $have
    | $existing + ($desired | map(select(.id as $i | ($have | index($i)) | not)))
  ')"

added="$(jq -n --argjson e "$existing_list" --argjson m "$merged_list" \
  '($m | length) - ($e | length)')"

if [[ "$added" -gt 0 ]]; then
  patch_file="$(mktemp)"
  jq -n --argjson list "$merged_list" '{ agents: { list: $list } }' > "$patch_file"
  openclaw config patch --file "$patch_file"
  rm -f "$patch_file"
  echo "    - added $added agent(s); list now has $(echo "$merged_list" | jq 'length')"
else
  echo "    - all demo agents already in agents.list — left as-is"
fi

# ---------------------------------------------------------------------------
# Step 4 — install skills straight into OpenClaw's own skills dir.
# OpenClaw natively discovers everything under ~/.openclaw/skills/, so we copy
# the repo's skills there directly — no staging into the plugin's skills/
# subdir and no reliance on the plugin symlink exposing it as plugin-skills.
# ---------------------------------------------------------------------------
SOURCE_SKILLS_DIR="$REPO_ROOT/skills"
DEST_SKILLS_DIR="$OPENCLAW_HOME/skills"

echo "==> Installing skills from $SOURCE_SKILLS_DIR into $DEST_SKILLS_DIR"

if [[ ! -d "$SOURCE_SKILLS_DIR" ]]; then
  echo "WARNING: source skills directory does not exist: $SOURCE_SKILLS_DIR" >&2
else
  mkdir -p "$DEST_SKILLS_DIR"
  shopt -s nullglob
  for skill_dir in "$SOURCE_SKILLS_DIR"/*/; do
    echo "    - $(basename "${skill_dir%/}")"
  done
  cp -rf "$SOURCE_SKILLS_DIR"/* "$DEST_SKILLS_DIR"/
  shopt -u nullglob
fi

# ---------------------------------------------------------------------------
# Step 5 — seed the bundled personas (cp -n: your edits are never clobbered).
# ---------------------------------------------------------------------------
echo "==> Seeding agent personas into $OPENCLAW_HOME/agents (cp -n, non-destructive)"
for agent_dir in "$PERSONA_DIR"/*/; do
  agent_id="$(basename "$agent_dir")"
  dst="$OPENCLAW_HOME/agents/$agent_id/workspace"
  mkdir -p "$dst" "$OPENCLAW_HOME/agents/$agent_id/agent"
  cp -n "$agent_dir/workspace/"*.md "$dst/" 2>/dev/null || true
  echo "    - $agent_id"
done

# ---------------------------------------------------------------------------
# Step 6 — plugin finalize (clean script): symlink the plugin in, validate the
# now-complete config, and restart the gateway so it loads plugin + agents.
# ---------------------------------------------------------------------------
echo "==> Finalizing the OpenClaw plugin (symlink + validate + gateway restart)"
finalize_args=(--openclaw-home "$OPENCLAW_HOME" --plugin-id "$PLUGIN_ID")
[[ "${SKIP_RESTART:-0}" == "1" ]] && finalize_args+=(--skip-restart)
bash "$PLUGIN_INSTALL_SH" finalize "${finalize_args[@]}"

# ---------------------------------------------------------------------------
# Step 7 — wake up the persona agents so their sessions/agent dirs exist.
# ---------------------------------------------------------------------------
if [[ "${SKIP_WAKEUP:-0}" == "1" ]]; then
  echo "==> SKIP_WAKEUP=1 — not waking agents"
else
  echo "==> Waking demo agents (creates each agent's session)"
  for agent_id in "${PERSONA_AGENTS[@]}"; do
    if openclaw agent -m "hi" --agent "$agent_id" >/dev/null 2>&1; then
      echo "    - $agent_id ✓"
    else
      echo "    ! $agent_id — wakeup failed (retry: openclaw agent -m \"hi\" --agent $agent_id)"
    fi
  done
fi

cat <<EOF

==> Done. Everything is automated — no manual openclaw.json editing required.

The adapter subscribes to the configured monitors on the Smart Community MCP server
($MCP_URL) and injects each new alert into the routed session(s).

Re-running this script is safe: personas, plugin config, and pre-existing agents
are never clobbered. To reconfigure monitors, edit
  plugins.entries.$PLUGIN_ID.config.monitors
in $OPENCLAW_HOME/openclaw.json (or via 'openclaw config set/patch') and restart.
EOF
