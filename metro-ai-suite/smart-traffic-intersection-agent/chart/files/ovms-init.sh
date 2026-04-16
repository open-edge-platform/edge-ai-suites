#!/bin/bash
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# OVMS Model Init Script (Helm init container)
# Runs inside python:3.12-slim.
# Pattern aligned with edge-ai-libraries sample apps (VSS, DocSum).
#
# Args (passed via Kubernetes args field):
#   $0 = VLM model name (e.g. microsoft/Phi-3.5-vision-instruct)
#   $1 = VLM weight format (e.g. int4)
#   $2 = HuggingFace token (optional)
#   $3 = VLM target device (e.g. GPU, CPU)

set -e

model=$0
weight_format=$1
hf_token=$2
target_device=$3

# Compute storage-aware model name: {sanitized}_{device}_{format}
sanitized=$(printf '%s' "$model" | sed 's#[^A-Za-z0-9_.-]#_#g')
case "$model" in
    OpenVINO/*) storage_name="${sanitized}_${target_device}" ;;
    *)          storage_name="${sanitized}_${target_device}_${weight_format}" ;;
esac

case "$target_device" in
    *GPU*|*NPU*) cache_size=2 ;;
    *)           cache_size=10 ;;
esac

echo "================================================================="
echo "OVMS Model Init (Helm)"
echo "  Model:          ${model}"
echo "  Storage Name:   ${storage_name}"
echo "  Target Device:  ${target_device}"
echo "  Weight Format:  ${weight_format}"
echo "  Cache Size:     ${cache_size}"
echo "================================================================="

# Install system deps (git needed by pip git+ refs, curl to fetch scripts)
apt-get update -qq && apt-get install -y -qq git curl > /dev/null 2>&1

# Install OVMS export dependencies
pip3 install -r https://raw.githubusercontent.com/openvinotoolkit/model_server/refs/tags/v2026.1/demos/common/export_models/requirements.txt
# Pin transformers to avoid DynamicCache.get_usable_length removal in newer versions
# (Phi-3.5-vision custom code depends on this API)
pip3 install 'transformers==4.53.3'
pip3 install -U 'huggingface_hub[hf_xet]==0.36.0'

# Log in to Hugging Face
if [ -n "${hf_token}" ]; then
    echo "Logging in to Hugging Face..."
    python3 -c "import huggingface_hub; huggingface_hub.login(token='${hf_token}')"
fi

# Download export script and run model conversion
curl -sSL https://raw.githubusercontent.com/openvinotoolkit/model_server/refs/tags/v2026.1/demos/common/export_models/export_model.py -o export_model.py
mkdir -p models

python3 export_model.py text_generation \
    --source_model "${model}" \
    --model_name "${storage_name}" \
    --weight-format "${weight_format}" \
    --config_file_path models/config.json \
    --model_repository_path models \
    --target_device "${target_device}" \
    --cache_size "${cache_size}" \
    --pipeline_type VLM_CB

cp -r models/* /models/

echo "================================================================="
echo "Model export complete: ${storage_name}"
echo "================================================================="
