# Deploy vLLM Service

This guide explains how to deploy the multimodal sample app with the vLLM service enabled using the Makefile targets.

## Prerequisites

1. Ensure `.env` is configured and includes valid values for:

   - `HOST_IP`
   - `INFLUXDB_USERNAME`, `INFLUXDB_PASSWORD`
   - `VISUALIZER_GRAFANA_USER`, `VISUALIZER_GRAFANA_PASSWORD`
   - `MTX_WEBRTCICESERVERS2_0_USERNAME`, `MTX_WEBRTCICESERVERS2_0_PASSWORD`
   - `S3_STORAGE_USERNAME`, `S3_STORAGE_PASSWORD`

## Download Models

1. Download `Qwen3.5 2B` model

> Please review the [Qwen3.5 2B license](https://huggingface.co/Qwen/Qwen3.5-2B/blob/main/LICENSE) before downloading.

```bash
mkdir -p config/vllm/huggingface && \
cd config/vllm/huggingface && \
rm -rf .modelenv && \
python3 -m venv .modelenv && \
source .modelenv/bin/activate && \
pip3 install huggingface_hub==1.23.0 && \
rm -rf Qwen3.5-2B && \
huggingface-cli download Qwen/Qwen3.5-2B --local-dir ./Qwen3.5-2B && \
deactivate && \
cd ../../..
```

2. Download `checkpoint-432` fine-tuned model

> To be Updated once model is huggingface

## Deploy the vLLM Service

Run:

```bash
make up_vllm
```

For a fresh build before deployment:

```bash
make build
make up_vllm
```

## Verify the Deployment

1. Check overall stack health:

   ```bash
   make status
   ```

2. Confirm the vLLM container is running:

   ```bash
   docker ps --filter "name=vllm-server"
   ```

3. Inspect vLLM logs:

   ```bash
   docker logs -f vllm-server
   ```

## Stop the Deployment

To bring down the full stack:

```bash
make down
```

## Troubleshooting

- `vllm-server` startup delay after deployment
   The `vllm-server` service can take about 10 minutes to fully come up after `make up_vllm`. This is expected while the model is initialized and loaded into memory.

- `Error: configs/vllm/models directory does not exist.`
  Create the directory and place the required model artifacts in it.

- `Error: configs/vllm/models directory is empty.`
  Add model files/checkpoints before running `make up_vllm`.

- `HOST_IP is not set` or `HOST_IP is not a valid IPv4 address format.`
  Update `HOST_IP` in `.env` with a valid IPv4 address.

- Username/password validation failures from `check_env_variables`
  Update `.env` values so they match the Makefile validation rules.