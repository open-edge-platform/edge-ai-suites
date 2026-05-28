# RAG Model Download

This guide covers the optional Live Video Captioning RAG setup. These steps are not required for the base Live Video Captioning application.

## What RAG needs

RAG uses:

- the base VLM model for Live Video Captioning in `ov_models/`,
- an LLM model cache in `llm_models/`,
- embedding service settings configured by `scripts/setup_embeddings.sh`.

## Download the LLM model

From the `live-video-captioning` directory:

```bash
./model_download_scripts/download_models.sh \
  --model Qwen/Qwen2.5-3B-Instruct \
  --type llm \
  --device CPU \
  --weight-format int8
```

The model is prepared under `llm_models/`.

For gated Hugging Face models, set a token first:

```bash
export HUGGINGFACEHUB_API_TOKEN=<your-huggingface-token>
```

## Review Embedding Defaults

The default embeddings and LLM settings are in:

```text
scripts/setup_embeddings.sh
```

Update these values only if you want different models or devices:

```bash
EMBEDDING_MODEL_NAME=QwenText/qwen3-embedding-0.6b
EMBEDDING_DEVICE=CPU
LLM_DEVICE=CPU
LLM_MODEL_ID=Qwen/Qwen2.5-3B-Instruct
```

## Enable RAG services

After downloading the LLM model, follow [Configure Embedding Creation with RAG](../configure-embedding-creation-with-rag.md) to enable the compose profile and start the RAG services.
