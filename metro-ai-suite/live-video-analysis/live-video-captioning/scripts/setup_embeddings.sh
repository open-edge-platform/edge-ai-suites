#!/bin/bash


# Configure models and devices for embedding and LLM
EMBEDDING_MODEL_NAME=QwenText/qwen3-embedding-0.6b
EMBEDDING_DEVICE="CPU"
LLM_DEVICE="CPU"
LLM_MODEL_ID="microsoft/Phi-3.5-mini-instruct"
MODEL_CACHE_PATH="${PWD}/llm_models"

export USER_GROUP_ID=$(id -g ${USER})
export MODEL_CACHE_PATH="$MODEL_CACHE_PATH"
export LLM_MODEL_ID="$LLM_MODEL_ID"
export LLM_DEVICE="$LLM_DEVICE"

export EMBEDDING_MODEL_NAME="$EMBEDDING_MODEL_NAME"
export EMBEDDING_HOST="multimodal-embedding-serving"
export EMBEDDING_HOST_PORT=8000
export EMBEDDING_SERVER_PORT=9777
export EMBEDDING_MODEL="$EMBEDDING_MODEL_NAME"
export EMBEDDING_DEVICE="$EMBEDDING_DEVICE"
export EMBEDDING_OV_MODELS_DIR=/app/ov_models
export EMBEDDING_USE_OV=true

# env for vdms-vector-db
export VDMS_HOST="vdms-vector-db"
export VDMS_PORT=55555

# env for embedding creation in live-video-captioning
export ENABLE_EMBEDDING=true
export COMPOSE_PROFILES=EMBEDDING

source scripts/setup.sh
