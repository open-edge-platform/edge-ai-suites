#!/bin/sh
set -e

MODEL_DIR="/models/ai-ecg"
BASE_URL="https://raw.githubusercontent.com/Einse57/OpenVINO_sample/master/ai-ecg-master"

MODELS="
ecg_8960_ir10_fp16.xml
ecg_8960_ir10_fp16.bin
ecg_17920_ir10_fp16.xml
ecg_17920_ir10_fp16.bin
"

echo "[INFO] Creating ECG model directory: ${MODEL_DIR}"
mkdir -p "${MODEL_DIR}"

for model in $MODELS; do
  if [ ! -f "${MODEL_DIR}/${model}" ]; then
    echo "[INFO] Downloading ${model}"
    wget -q "${BASE_URL}/${model}" -O "${MODEL_DIR}/${model}"
  else
    echo "[INFO] ${model} already exists, skipping"
  fi
done

echo "[INFO] ECG models ready"
