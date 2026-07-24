#!/usr/bin/env bash
#
# fire_models.sh — re-apply this developer's hand-configured model providers into
# a freshly-installed ~/.openclaw/openclaw.json, so you don't have to reconfigure
# models by hand after every clean reinstall.
#
# It is a DEV CONVENIENCE, not part of the clean OpenClaw install: it encodes the
# specific providers this machine uses (minimax cloud + a local vLLM). Edit the
# heredoc below to match your own providers.
#
# Uses `openclaw config patch` (validated recursive object-merge). Provider objects
# merge in without disturbing other providers; the models[] arrays are replaced with
# the full definitions given here.
#
# Prereqs:
#   - openclaw CLI installed and ~/.openclaw initialized (run onboard first)
#   - MINIMAX_API_KEY exported or present in ~/.openclaw/.env (referenced, not baked)
#
# Env overrides:
#   OPENCLAW_HOME    target home        (default: ~/.openclaw)
#   SKIP_RESTART=1   don't restart the gateway after patching
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
CONFIG="$OPENCLAW_HOME/openclaw.json"

command -v openclaw >/dev/null 2>&1 || { echo "ERROR: 'openclaw' CLI not found on PATH." >&2; exit 1; }
[[ -f "$CONFIG" ]] || { echo "ERROR: $CONFIG not found — run 'openclaw onboard --install-daemon' first." >&2; exit 1; }

echo "==> Backing up $CONFIG"
cp -f "$CONFIG" "$CONFIG.fire_models.bak.$(date +%s)"

echo "==> Patching model providers into openclaw.json"
patch_file="$(mktemp)"
cat > "$patch_file" <<'JSON5'
{
  agents: {
    defaults: {
      models: {
        "minimax/MiniMax-M3": { alias: "Minimax" },
        "vllm-local/Qwen/Qwen3.5-35B-A3B": { alias: "Qwen3.5" }
      },
      model: { primary: "Qwen3.5" }
    }
  },
  models: {
    mode: "merge",
    providers: {
      minimax: {
        baseUrl: "https://api.minimaxi.com/anthropic",
        apiKey: "${MINIMAX_API_KEY}",
        api: "anthropic-messages",
        authHeader: true,
        models: [
          {
            id: "MiniMax-M3",
            name: "MiniMax M3",
            reasoning: true,
            input: ["text", "image"],
            cost: { input: 0.6, output: 2.4, cacheRead: 0.12, cacheWrite: 0 },
            contextWindow: 1000000,
            maxTokens: 131072
          }
        ]
      },
      "vllm-local": {
        baseUrl: "http://localhost:41091/v1",
        apiKey: "none",
        api: "openai-completions",
        models: [
          {
            id: "Qwen/Qwen3.5-35B-A3B",
            name: "Qwen/Qwen3.5-35B-A3B",
            reasoning: true,
            input: ["text", "image"],
            cost: { input: 0.01, output: 0.01, cacheRead: 0, cacheWrite: 0 },
            contextWindow: 61440,
            maxTokens: 4096
          }
        ]
      }
    }
  }
}
JSON5
openclaw config patch --file "$patch_file"
rm -f "$patch_file"

echo "==> Validating openclaw.json"
openclaw config validate

if [[ "${SKIP_RESTART:-0}" == "1" ]]; then
  echo "==> SKIP_RESTART=1 — not restarting the gateway"
else
  echo "==> Restarting the OpenClaw gateway"
  openclaw gateway restart 2>/dev/null || echo "    ! restart failed — start it manually: openclaw gateway run"
fi

echo "==> Writing MINIMAX_API_KEY placeholder to $OPENCLAW_HOME/.env"
echo "MINIMAX_API_KEY=your-api-key" >> "$OPENCLAW_HOME/.env"
cat <<EOF

==> Done. Providers applied: minimax (Minimax), vllm-local (Qwen3.5); default = Qwen3.5.

Make sure the referenced secret is available (referenced as \${MINIMAX_API_KEY}, not baked in) at $OPENCLAW_HOME/.env
EOF
