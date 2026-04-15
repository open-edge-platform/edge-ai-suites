#!/bin/bash
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# OVMS Model Init Script (Helm init container)
# Runs inside the OVMS image — uses pip3, curl, python directly.
# Receives parameters via positional args from the deployment template.
#
# Args (passed via Kubernetes args field):
#   $0 = VLM model name
#   $1 = VLM weight format
#   $2 = HuggingFace token (optional)
#   $3 = VLM target device

set -e

vlm_model=$0
vlm_weight_format=$1
huggingface_token=$2
vlm_target_device=$3

# === Helper functions ===

sanitize_name() {
    printf '%s' "$1" | sed 's#[^A-Za-z0-9_.-]#_#g'
}

is_openvino_namespace_model() {
    case "$1" in
        OpenVINO/*) return 0 ;;
        *) return 1 ;;
    esac
}

get_cache_size() {
    local device="$1"
    case "$device" in
        *GPU*|*NPU*) echo "2" ;;
        *) echo "10" ;;
    esac
}

get_storage_model_name() {
    local model="$1"
    local device="$2"
    local format="$3"
    local sanitized
    sanitized=$(sanitize_name "$model")

    if is_openvino_namespace_model "$model"; then
        printf '%s_%s' "$sanitized" "$device"
    else
        printf '%s_%s_%s' "$sanitized" "$device" "$format"
    fi
}

# === Main ===

vlm_storage_name=$(get_storage_model_name "$vlm_model" "$vlm_target_device" "$vlm_weight_format")
vlm_cache_size=$(get_cache_size "$vlm_target_device")

echo "================================================================="
echo "OVMS Model Init (Helm)"
echo "  VLM Model:        ${vlm_model}"
echo "  Storage Name:     ${vlm_storage_name}"
echo "  Target Device:    ${vlm_target_device}"
echo "  Weight Format:    ${vlm_weight_format}"
echo "  Cache Size:       ${vlm_cache_size}"
echo "================================================================="

# Install dependencies based on model type
if is_openvino_namespace_model "$vlm_model"; then
    echo "OpenVINO namespace model detected. Installing lightweight dependencies..."
    pip3 install --no-cache-dir 'huggingface_hub<0.27' jinja2
else
    echo "Installing full conversion dependencies..."
    requirements_url="https://raw.githubusercontent.com/openvinotoolkit/model_server/refs/tags/v2026.1/demos/common/export_models/requirements.txt"
    tmp_requirements=$(mktemp)
    curl -fsSL "${requirements_url}" -o "${tmp_requirements}"
    if grep -q '^transformers' "${tmp_requirements}"; then
        sed -i 's/^transformers.*/transformers==4.53.3/' "${tmp_requirements}"
    else
        echo 'transformers==4.53.3' >> "${tmp_requirements}"
    fi
    pip3 install --no-cache-dir -r "${tmp_requirements}"
    rm -f "${tmp_requirements}"
fi

pip3 install --no-cache-dir -U 'huggingface_hub[hf_xet]==0.36.0'

if [ -n "${huggingface_token}" ]; then
    echo "Logging in to Hugging Face..."
    hf auth login --token "${huggingface_token}"
fi

curl -fsSL https://raw.githubusercontent.com/openvinotoolkit/model_server/refs/tags/v2026.1/demos/common/export_models/export_model.py -o export_model.py
mkdir -p models

# Export VLM model with storage-aware name
python export_model.py text_generation \
    --source_model "${vlm_model}" \
    --model_name "${vlm_storage_name}" \
    --weight-format "${vlm_weight_format}" \
    --config_file_path models/config.json \
    --model_repository_path models \
    --target_device "${vlm_target_device}" \
    --cache_size "${vlm_cache_size}" \
    --pipeline_type VLM_CB

cp -r models/* /models/

echo "================================================================="
echo "Model export complete: ${vlm_storage_name}"
echo "================================================================="
