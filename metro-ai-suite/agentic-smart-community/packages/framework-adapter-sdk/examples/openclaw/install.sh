#!/usr/bin/env bash
#
# One-shot install for the smartbuilding-alerts OpenClaw framework adapter.
#
#   1. build the framework-adapter-sdk (this plugin imports its built dist)
#   2. install the plugin's own deps (links the SDK into node_modules)
#   3. register the plugin entry in openclaw.json          (openclaw config patch)
#   4. merge the demo agents into agents.list[]            (merge-by-id, non-destructive)
#   5. symlink the plugin into ~/.openclaw/extensions/     (AFTER config — see note below)
#   6. copy the bundled agent personas into ~/.openclaw/agents/  (cp -n: never clobbers)
#   7. restart the OpenClaw gateway                        (openclaw gateway restart)
#   8. wake up the demo agents so their sessions exist     (openclaw agent -m hi)
#
# Config is written BEFORE the symlink on purpose: OpenClaw enforces the plugin's
# required-field schema the instant it's discovered (symlinked), so a symlink without
# config makes the whole config invalid and blocks `config patch`. See the note inline.
#
# Fully automated & idempotent: safe to re-run — and self-heals a half-finished run.
# The persona copy, plugin config, and agents you added yourself are never clobbered.
#
# Env overrides:
#   OPENCLAW_HOME   target home                       (default: ~/.openclaw)
#   MCP_URL         SmartBuilding MCP endpoint         (default: http://localhost:3100/mcp)
#   AGENT_MODEL     model alias for the demo agents    (default: Qwen3.5)
#   SKIP_RESTART=1  skip the gateway restart (step 7)
#   SKIP_WAKEUP=1   skip the agent wakeup   (step 8)
set -euo pipefail

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
HERE="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
SDK_DIR="$(cd "$HERE/../.." && pwd)"                 # packages/framework-adapter-sdk
REPO_ROOT="$(cd "$SDK_DIR/../.." && pwd)"            # repo root
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
PLUGIN_ID="smartbuilding-alerts"
MCP_URL="${MCP_URL:-http://localhost:3100/mcp}"
AGENT_MODEL="${AGENT_MODEL:-Qwen3.5}"

# Demo agents (id order matters: `main` first — it is OpenClaw's default agent).
# The 3 persona agents below are the ones with bundled workspaces under agents/.
PERSONA_AGENTS=(fridge-agent child-safety-agent elder-wakeup-agent)

command -v openclaw >/dev/null 2>&1 || { echo "ERROR: 'openclaw' CLI not found on PATH." >&2; exit 1; }
command -v jq       >/dev/null 2>&1 || { echo "ERROR: 'jq' not found on PATH."       >&2; exit 1; }

echo "==> Building framework-adapter-sdk"
npm --prefix "$REPO_ROOT" -w @smartbuilding-video/framework-adapter-sdk run build

echo "==> Installing plugin dependencies"
npm --prefix "$HERE" install

# ---------------------------------------------------------------------------
# CONFIG MUST BE WRITTEN BEFORE THE SYMLINK.
# The plugin declares a configSchema with required mcpServer/monitors and activates
# onStartup. OpenClaw enforces that schema the moment the plugin is *discovered* (i.e.
# symlinked into extensions/). If the symlink exists but the config is absent, the whole
# openclaw.json is "invalid" and `openclaw config patch` refuses to run — a chicken-and-egg
# deadlock. So we (a) remove any pre-existing link, (b) write the config, then (c) relink.
# Removing the link first also self-heals a half-finished prior run.
# ---------------------------------------------------------------------------
echo "==> Unlinking plugin while we write config (avoids schema deadlock)"
rm -f "$OPENCLAW_HOME/extensions/$PLUGIN_ID"

# ---------------------------------------------------------------------------
# Register the plugin entry in openclaw.json (object-merge, idempotent).
# `openclaw config patch` merges objects recursively and validates before writing,
# so this never disturbs the other plugins (minimax/tavily/…). We only write when
# the entry is absent, to preserve any hand edits to monitors/mcpServer on re-run.
# ---------------------------------------------------------------------------
echo "==> Registering plugin entry in openclaw.json"
if openclaw config get "plugins.entries.$PLUGIN_ID" --json >/dev/null 2>&1; then
  echo "    - plugins.entries.$PLUGIN_ID already present — left as-is"
else
  patch_file="$(mktemp)"
  cat > "$patch_file" <<EOF
{
  plugins: {
    entries: {
      "$PLUGIN_ID": {
        enabled: true,
        config: {
          mcpServer: { url: "$MCP_URL" },
          monitors: {
            cam_child: {
              alerts: [
                { agentId: "child-safety-agent", sessionKey: "agent:child-safety-agent:cam_child", deliver: false }
              ]
            },
            cam_elder_bedroom: {
              alerts: [
                { agentId: "elder-wakeup-agent", sessionKey: "agent:elder-wakeup-agent:cam_elder_bedroom", deliver: false }
              ]
            }
          }
        }
      }
    }
  }
}
EOF
  openclaw config patch --file "$patch_file"
  rm -f "$patch_file"
  echo "    - registered $PLUGIN_ID (mcpServer=$MCP_URL)"
fi

# ---------------------------------------------------------------------------
# Step 6 — merge the demo agents into agents.list[] (merge-by-id, non-destructive).
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
# Config is written and valid — NOW link the plugin in and seed personas.
# ---------------------------------------------------------------------------
echo "==> Symlinking plugin into $OPENCLAW_HOME/extensions/$PLUGIN_ID"
mkdir -p "$OPENCLAW_HOME/extensions"
ln -sfn "$HERE" "$OPENCLAW_HOME/extensions/$PLUGIN_ID"

SOURCE_SKILLS_DIR="$REPO_ROOT/skills"
PLUGIN_SKILLS_SOURCE_DIR="$HERE/skills"

echo "==> Staging plugin skills from $SOURCE_SKILLS_DIR into $PLUGIN_SKILLS_SOURCE_DIR"

if [[ ! -d "$SOURCE_SKILLS_DIR" ]]; then
  echo "WARNING: source skills directory does not exist: $SOURCE_SKILLS_DIR" >&2
else
  mkdir -p "$PLUGIN_SKILLS_SOURCE_DIR"
  shopt -s nullglob
  for skill_dir in "$SOURCE_SKILLS_DIR"/*/; do
    skill_dir="${skill_dir%/}"
    skill_id="$(basename "$skill_dir")"
    echo "    - $skill_id"
    rm -rf "$PLUGIN_SKILLS_SOURCE_DIR/$skill_id"
    cp -a "$skill_dir" "$PLUGIN_SKILLS_SOURCE_DIR/$skill_id"
  done
  shopt -u nullglob
fi

echo "==> Seeding agent personas into $OPENCLAW_HOME/agents (cp -n, non-destructive)"
for agent_dir in "$HERE"/agents/*/; do
  agent_id="$(basename "$agent_dir")"
  dst="$OPENCLAW_HOME/agents/$agent_id/workspace"
  mkdir -p "$dst" "$OPENCLAW_HOME/agents/$agent_id/agent"
  cp -n "$agent_dir/workspace/"*.md "$dst/" 2>/dev/null || true
  echo "    - $agent_id"
done

echo "==> Validating openclaw.json (plugin now discovered + configured)"
openclaw config validate

# ---------------------------------------------------------------------------
# Step 7 — restart the gateway so it loads the new plugin + agents.
# ---------------------------------------------------------------------------
if [[ "${SKIP_RESTART:-0}" == "1" ]]; then
  echo "==> SKIP_RESTART=1 — not restarting the gateway"
else
  echo "==> Restarting the OpenClaw gateway"
  if openclaw gateway restart 2>/dev/null; then
    # Poll until the gateway answers (connectivity probe ok), up to ~30s.
    for _ in $(seq 1 30); do
      if openclaw gateway status 2>/dev/null | grep -qi "Connectivity probe: ok"; then
        echo "    - gateway is up"
        break
      fi
      sleep 1
    done
  else
    echo "    ! 'openclaw gateway restart' failed (gateway not installed as a service?)."
    echo "    ! Start it manually, e.g.:  openclaw gateway --force --port 18789"
  fi
fi

# ---------------------------------------------------------------------------
# Step 8 — wake up the persona agents so their sessions/agent dirs exist.
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

The adapter subscribes to the configured monitors on the SmartBuilding MCP server
($MCP_URL) and injects each new alert into the routed session(s).

Re-running this script is safe: personas, plugin config, and pre-existing agents
are never clobbered. To reconfigure monitors, edit
  plugins.entries.$PLUGIN_ID.config.monitors
in $OPENCLAW_HOME/openclaw.json (or via 'openclaw config set/patch') and restart.
EOF
