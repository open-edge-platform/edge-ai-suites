#!/bin/bash

MODEL_CACHE_PATH="${PWD}/llm_models"
DEVICE="CPU"

export USER_GROUP_ID=$(id -g ${USER})
export MODEL_CACHE_PATH="$MODEL_CACHE_PATH"
export LLM_MODEL_ID="microsoft/Phi-3.5-mini-instruct"
export LLM_DEVICE="$DEVICE"

export EMBEDDING_MODEL_NAME=QwenText/qwen3-embedding-0.6b
export VDMS_HOST="vdms-vector-db"
export VDMS_PORT="55555"
export EMBEDDING_MODEL="${EMBEDDING_MODEL_NAME}"
export EMBEDDING_HOST="multimodal-embedding-serving"
export EMBEDDING_HOST_PORT=8000

export EMBEDDING_OV_MODELS_DIR=/app/ov_models
export EMBEDDING_SERVER_PORT=9777
export EMBEDDING_DEVICE="$DEVICE"
export EMBEDDING_USE_OV=true

# env for vdms-vector-db
export VDMS_VDB_HOST_PORT=55555
export VDMS_VDB_HOST=vdms-vector-db

source scripts/setup.sh
