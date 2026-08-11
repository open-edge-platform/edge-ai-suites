#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
CONFIG="${OPENCLAW_HOME}/openclaw.json"
MODEL_BASE_URL="${MODEL_BASE_URL:-http://localhost:41091/v1}"
SKIP_RESTART="${SKIP_RESTART:-0}"

command -v curl >/dev/null 2>&1 || { echo "ERROR: 'curl' is required." >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' is required." >&2; exit 1; }
command -v openclaw >/dev/null 2>&1 || { echo "ERROR: 'openclaw' CLI not found on PATH." >&2; exit 1; }
[[ -f "$CONFIG" ]] || { echo "ERROR: $CONFIG not found. Run 'openclaw onboard --install-daemon' first." >&2; exit 1; }

echo "==> Discovering the deployed model at ${MODEL_BASE_URL}/models"
models_response="$(curl --fail --silent --show-error --max-time 10 "${MODEL_BASE_URL}/models")"
model_id="$(jq -er '.data[0].id | select(type == "string" and length > 0)' <<<"$models_response")" || {
	echo "ERROR: No valid model ID was returned by ${MODEL_BASE_URL}/models." >&2
	exit 1
}
context_window="$(jq -er '.data[0].max_model_len | select(type == "number" and . > 0)' <<<"$models_response" 2>/dev/null || printf '61440')"
model_ref="vllm-local/${model_id}"

echo "==> Backing up $CONFIG"
backup="${CONFIG}.configure_local_model.bak.$(date +%s)"
cp --preserve=mode,ownership,timestamps "$CONFIG" "$backup"

patch_file="$(mktemp)"
trap 'rm -f "$patch_file"' EXIT
jq -n \
	--arg base_url "$MODEL_BASE_URL" \
	--arg model_id "$model_id" \
	--arg model_ref "$model_ref" \
	--argjson context_window "$context_window" \
	'{
		agents: {
			defaults: {
				models: {
					($model_ref): {alias: $model_id}
				},
				model: {primary: $model_ref}
			}
		},
		models: {
			mode: "merge",
			providers: {
				"vllm-local": {
					baseUrl: $base_url,
					apiKey: "none",
					api: "openai-completions",
					models: [
						{
							id: $model_id,
							name: $model_id,
							reasoning: true,
							input: ["text", "image"],
							cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0},
							contextWindow: $context_window,
							maxTokens: 4096
						}
					]
				}
			}
		}
	}' >"$patch_file"

echo "==> Adding vllm-local and setting ${model_ref} as the default model"
openclaw config patch --file "$patch_file"
openclaw config validate

if [[ "$SKIP_RESTART" == "1" ]]; then
	echo "==> SKIP_RESTART=1; gateway restart skipped"
else
	echo "==> Restarting the OpenClaw gateway"
	openclaw gateway restart
fi

echo "==> Done. Existing model configuration was preserved; default model: ${model_ref}"
