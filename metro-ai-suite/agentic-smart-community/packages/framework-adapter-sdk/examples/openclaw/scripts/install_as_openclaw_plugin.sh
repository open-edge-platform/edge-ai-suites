#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║        Install this example as an OpenClaw plugin (clean)        ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Plugin-only install. Nothing demo-specific: no agents, no       ║
# ║  personas, no skills, no monitor routes, no models, no cron.     ║
# ║                                                                  ║
# ║  Steps (subcommand 'all', the default):                          ║
# ║    prepare   1. build the framework-adapter-sdk (plugin imports  ║
# ║                 its compiled dist)                               ║
# ║              2. install the plugin's own npm deps                ║
# ║              3. unlink it from OPENCLAW_HOME/extensions          ║
# ║      (all)   4. register a minimal plugins.entries.<id> if the   ║
# ║                 entry is absent (schema needs mcpServer+monitors)║
# ║    finalize  5. symlink the plugin into extensions/<id>          ║
# ║              6. openclaw config validate                         ║
# ║              7. restart the gateway and wait for it              ║
# ║                                                                  ║
# ║  Step 3 before step 4 is deliberate: the plugin activates        ║
# ║  onStartup and its configSchema requires mcpServer + monitors,   ║
# ║  and OpenClaw enforces that schema the moment the plugin is      ║
# ║  *discovered* (symlinked). A symlink without config makes the    ║
# ║  whole openclaw.json invalid, and then 'openclaw config patch'   ║
# ║  refuses to run — a deadlock. Unlinking first also self-heals a  ║
# ║  half-finished previous run.                                     ║
# ║                                                                  ║
# ║  Callers that write their own plugin config (routes, agents, …)  ║
# ║  should drive the two halves instead of 'all', and do their own  ║
# ║  config work in between, while the plugin is unlinked:           ║
# ║                                                                  ║
# ║      bash install_as_openclaw_plugin.sh prepare                  ║
# ║      # ... write plugins.entries.<id>.config, agents, skills ... ║
# ║      bash install_as_openclaw_plugin.sh finalize                 ║
# ║                                                                  ║
# ║  Idempotent: safe to re-run. An existing plugin entry is never   ║
# ║  overwritten.                                                    ║
# ║                                                                  ║
# ║  Usage:                                                          ║
# ║    bash install_as_openclaw_plugin.sh [all|prepare|finalize] [opts]
# ║                                                                  ║
# ║  Options / env overrides:                                        ║
# ║    --openclaw-home DIR   OPENCLAW_HOME   (default: ~/.openclaw)  ║
# ║    --mcp-url URL         MCP_URL         (default: from schema)  ║
# ║    --plugin-id ID        PLUGIN_ID       (default: openclaw.plugin.json id)
# ║    --skip-build          SKIP_BUILD=1    reuse the existing dist ║
# ║    --skip-restart        SKIP_RESTART=1  don't touch the gateway ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

HERE="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
PLUGIN_DIR="$(cd "$HERE/.." && pwd)"                        # examples/openclaw
SDK_DIR="$(cd "$HERE/../../.." && pwd)"                     # packages/framework-adapter-sdk
COMPONENT_ROOT="$(cd "$HERE/../../../../.." && pwd)"        # npm workspace root

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
# Keep it out of the child environment: the `openclaw` CLI reads OPENCLAW_HOME as a
# $HOME override and would then look for $OPENCLAW_HOME/.openclaw/openclaw.json.
export -n OPENCLAW_HOME
MCP_URL="${MCP_URL:-http://localhost:3100/mcp}"
PLUGIN_ID="${PLUGIN_ID:-}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_RESTART="${SKIP_RESTART:-0}"
STAGE=all

while [[ $# -gt 0 ]]; do
  case "$1" in
    all|prepare|finalize) STAGE="$1" ;;
    --openclaw-home) OPENCLAW_HOME="$2"; shift ;;
    --mcp-url)       MCP_URL="$2";       shift ;;
    --plugin-id)     PLUGIN_ID="$2";     shift ;;
    --skip-build)    SKIP_BUILD=1 ;;
    --skip-restart)  SKIP_RESTART=1 ;;
    -h|--help) sed -n '2,50p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2
       echo "Usage: bash install_as_openclaw_plugin.sh [all|prepare|finalize] [--openclaw-home DIR] [--mcp-url URL] [--plugin-id ID] [--skip-build] [--skip-restart]" >&2
       exit 1 ;;
  esac
  shift
done

info() { echo "[ ok ] $*"; }
warn() { echo "[warn] $*"; }
title(){ echo ""; echo ">>> $*"; }


command -v openclaw >/dev/null 2>&1 || { echo "ERROR: 'openclaw' CLI not found on PATH." >&2; exit 1; }
command -v npm      >/dev/null 2>&1 || { echo "ERROR: 'npm' not found on PATH."      >&2; exit 1; }
command -v jq       >/dev/null 2>&1 || { echo "ERROR: 'jq' not found on PATH."       >&2; exit 1; }
[[ -f "$PLUGIN_DIR/package.json" ]]        || { echo "ERROR: plugin not found: $PLUGIN_DIR" >&2; exit 1; }
[[ -f "$PLUGIN_DIR/openclaw.plugin.json" ]]|| { echo "ERROR: openclaw.plugin.json not found in $PLUGIN_DIR" >&2; exit 1; }
[[ -f "$SDK_DIR/package.json" ]]           || { echo "ERROR: framework-adapter-sdk not found: $SDK_DIR" >&2; exit 1; }
[[ -f "$COMPONENT_ROOT/package.json" ]]    || { echo "ERROR: npm workspace root not found: $COMPONENT_ROOT" >&2; exit 1; }

# The extension dir name must match the id in openclaw.plugin.json, which is also
# the plugins.entries key OpenClaw looks the config up under.
if [[ -z "$PLUGIN_ID" ]]; then
  PLUGIN_ID="$(jq -r '.id // empty' "$PLUGIN_DIR/openclaw.plugin.json")"
fi
[[ -n "$PLUGIN_ID" ]] || { echo "ERROR: no plugin id in $PLUGIN_DIR/openclaw.plugin.json (pass --plugin-id)." >&2; exit 1; }
SDK_PKG="$(jq -r '.name' "$SDK_DIR/package.json")"
DB_DIR="$COMPONENT_ROOT/packages/db"
[[ -f "$DB_DIR/package.json" ]] || { echo "ERROR: database workspace not found: $DB_DIR" >&2; exit 1; }
DB_PKG="$(jq -r '.name' "$DB_DIR/package.json")"

run_prepare() {
  title "Step 1: build $DB_PKG and $SDK_PKG"
  if [[ "$SKIP_BUILD" == "1" ]]; then
    info "SKIP_BUILD=1 — reusing $SDK_DIR/dist"
  else
    npm --prefix "$COMPONENT_ROOT" -w "$DB_PKG" run build
    info "$DB_PKG built"
    npm --prefix "$COMPONENT_ROOT" -w "$SDK_PKG" run build
    info "SDK built"
  fi

  title "Step 2: install plugin dependencies"
  npm --prefix "$PLUGIN_DIR" install
  info "Plugin deps installed (SDK linked into node_modules)"

  # See the header note: config must be writable, so the plugin must not be
  # discovered while we (or our caller) patch openclaw.json.
  title "Step 3: unlink the plugin while config is written"
  rm -f "$OPENCLAW_HOME/extensions/$PLUGIN_ID"
  info "$OPENCLAW_HOME/extensions/$PLUGIN_ID is unlinked"
}

# Minimal registration only — an empty monitors map routes nothing. Real
# deployments add their own routes afterwards (or use prepare/finalize).
run_register() {
  title "Step 4: register plugins.entries.$PLUGIN_ID"
  if openclaw config get "plugins.entries.$PLUGIN_ID" --json >/dev/null 2>&1; then
    info "Entry already present — left as-is (mcpServer/monitors untouched)"
    return
  fi
  local patch_file
  patch_file="$(mktemp)"
  jq -n --arg id "$PLUGIN_ID" --arg url "$MCP_URL" '{
    plugins: { entries: { ($id): {
      enabled: true,
      config: { mcpServer: { url: $url }, monitors: {} }
    } } }
  }' > "$patch_file"
  openclaw config patch --file "$patch_file"
  rm -f "$patch_file"
  info "Registered $PLUGIN_ID (mcpServer.url=$MCP_URL, monitors={})"
}

run_finalize() {
  title "Step 5: symlink the plugin into $OPENCLAW_HOME/extensions/$PLUGIN_ID"
  mkdir -p "$OPENCLAW_HOME/extensions"
  ln -sfn "$PLUGIN_DIR" "$OPENCLAW_HOME/extensions/$PLUGIN_ID"
  info "Linked -> $PLUGIN_DIR"

  title "Step 6: validate openclaw.json (plugin now discovered + configured)"
  openclaw config validate

  title "Step 7: restart the OpenClaw gateway"
  if [[ "$SKIP_RESTART" == "1" ]]; then
    info "SKIP_RESTART=1 — restart the gateway yourself to load the plugin"
    return
  fi
  if openclaw gateway restart 2>/dev/null; then
    for _ in $(seq 1 30); do
      if openclaw gateway status 2>/dev/null | grep -qi "Connectivity probe: ok"; then
        info "Gateway is up"
        return
      fi
      sleep 1
    done
    warn "Gateway restarted but did not report a healthy probe within 30s"
  else
    warn "'openclaw gateway restart' failed (gateway not installed as a service?)"
    warn "Start it manually, e.g.:  openclaw gateway --force --port 18789"
  fi
}

case "$STAGE" in
  prepare)  run_prepare ;;
  finalize) run_finalize ;;
  all)      run_prepare; run_register; run_finalize ;;
esac

if [[ "$STAGE" == "prepare" ]]; then
  cat <<EOF

==========================================
  Plugin prepared (not linked yet).
==========================================

The plugin is built and its deps are installed, and it is intentionally NOT
linked into $OPENCLAW_HOME/extensions — so openclaw.json is patchable right now.

Next: write plugins.entries.$PLUGIN_ID.config (mcpServer + monitors), then run
  bash $HERE/$(basename "$0") finalize
EOF
else
  cat <<EOF

==========================================
  Plugin installed: $PLUGIN_ID
==========================================

  extension     : $OPENCLAW_HOME/extensions/$PLUGIN_ID -> $PLUGIN_DIR
  plugin-skills : $OPENCLAW_HOME/plugin-skills/configure-agent-alert-push -> $PLUGIN_DIR/skills/configure-agent-alert-push
  config        : plugins.entries.$PLUGIN_ID in $OPENCLAW_HOME/openclaw.json
EOF
fi
