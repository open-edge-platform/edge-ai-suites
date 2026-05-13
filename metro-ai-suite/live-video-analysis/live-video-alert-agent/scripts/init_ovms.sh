#!/usr/bin/env bash
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


# Environment variables (set via docker-compose):
#     VLM_NAME            OVMS servable name for the VLM model
#     VLM_REPO            HuggingFace repo ID for the VLM model
#     VLM_TARGET_DEVICE   OpenVINO target device for VLM (CPU, GPU)
#     LLM_NAME            OVMS servable name for the LLM model
#     LLM_REPO            HuggingFace repo ID for the LLM model
#     LLM_TARGET_DEVICE   OpenVINO target device for LLM (CPU, GPU)
#     HF_TOKEN            HuggingFace token for gated models (optional)

set -euo pipefail

VLM_REPO="${VLM_REPO}"
VLM_NAME="${VLM_REPO#*/}"
VLM_DEVICE="${VLM_TARGET_DEVICE:-${OVMS_TARGET_DEVICE:-CPU}}"
USE_ADK="${USE_ADK:-true}"
LLM_REPO="${LLM_REPO}"
LLM_NAME="${LLM_REPO#*/}"
LLM_DEVICE="${LLM_TARGET_DEVICE:-${OVMS_TARGET_DEVICE:-CPU}}"

REPO="/models"

#GPU Configuration
# Check if render device exist
if compgen -G "/dev/dri/render*" > /dev/null; then
    echo -e "\nRENDER device exist. Getting the GID...\n"
    export RENDER_DEVICE_GID=$(stat -c "%g" /dev/dri/render* | head -n 1)

else
    echo -e "\nNo RENDER device found. Defaulting GID to 1000...\n"
    export RENDER_DEVICE_GID=1000
fi

# ------------------------------------------------------------------
# Pull VLM model
# ------------------------------------------------------------------

echo "[init] Pulling VLM: ${VLM_REPO} -> ${VLM_NAME} (device=${VLM_DEVICE})"
ovms --pull \
    --source_model "${VLM_REPO}" \
    --model_repository_path "${REPO}" \
    --model_name "${VLM_NAME}" \
    --target_device "${VLM_DEVICE}" \
    --task text_generation \
    --pipeline_type VLM \
    --cache_size 12 \
    --enable_prefix_caching true \
    --max_num_batched_tokens 2048 \
    --max_num_seqs 16 \
    --kv_cache_precision u8 \
    --plugin_config '{"DYNAMIC_QUANTIZATION_GROUP_SIZE":"32","NUM_STREAMS":"2"}'
echo "[init] VLM pull complete"
VLM_PATH="${REPO}/${VLM_REPO}"

cat > "${REPO}/config_vlm.json" <<EOF
{
  "model_config_list": [
    {
      "config": {
        "name": "${VLM_NAME}",
        "base_path": "${VLM_PATH}"
      }
    }
  ]
}
EOF
echo "[init] Wrote ${REPO}/config_vlm.json"
# ------------------------------------------------------------------
# Pull LLM model
# ------------------------------------------------------------------

if [[ "${USE_ADK}" == "true" ]]; then
    echo "[init] Pulling LLM: ${LLM_REPO} -> ${LLM_NAME} (device=${LLM_DEVICE})"
    ovms --pull \
        --source_model "${LLM_REPO}" \
        --model_repository_path "${REPO}" \
        --model_name "${LLM_NAME}" \
        --target_device "${LLM_DEVICE}" \
        --task text_generation \
        --cache_size 6 \
        --enable_prefix_caching true \
        --max_num_batched_tokens 1024 \
        --max_num_seqs 8 \
        --kv_cache_precision u8 \
        --plugin_config '{"DYNAMIC_QUANTIZATION_GROUP_SIZE":"32","NUM_STREAMS":"2"}'
    echo "[init] LLM pull complete"
    
    LLM_PATH="${REPO}/${LLM_REPO}"
    cat > "${REPO}/config_llm.json" <<EOF
      {
        "model_config_list": [
          {
            "config": {
              "name": "${LLM_NAME}",
              "base_path": "${LLM_PATH}"
            }
          }
        ]
      }
EOF
echo "[init] Wrote ${REPO}/config_llm.json"
else
    echo "[init] Skipping LLM pull and config since USE_ADK is set to false"
    
fi

chown -R 5000:5000 "${REPO}"
chmod -R 755 "${REPO}"

echo "[init] OVMS model preparation complete"
