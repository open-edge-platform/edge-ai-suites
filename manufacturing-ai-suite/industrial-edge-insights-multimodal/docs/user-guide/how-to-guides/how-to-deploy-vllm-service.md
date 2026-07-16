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

**Download `Qwen3.5 2B` model and `Qwen 3.5 2B fine tuned LoRA adapter`**

> Please review and accept the [Qwen3.5 2B license](https://huggingface.co/Qwen/Qwen3.5-2B/blob/main/LICENSE) before downloading.
>
> The LoRA adapter was specifically trained on a subset of the [Intel Robotic Welding Multimodal Dataset](https://huggingface.co/datasets/IntelLabs/Intel_Robotic_Welding_Multimodal_Dataset) and may not generalize to generic weld datasets.

```bash
mkdir -p configs/vllm/huggingface configs/vllm/models && \
cd configs/vllm/ && \
rm -rf .modelenv && \
python3 -m venv .modelenv && \
source .modelenv/bin/activate && \
pip3 install huggingface_hub==1.23.0 && \
rm -rf huggingface models && \
hf download Qwen/Qwen3.5-2B \
    --local-dir ./huggingface/Qwen3.5-2B && \
hf download Intel/qwen3.5-2b-vlm-weld-explainability-lora \
    --local-dir ./models/qwen3.5-2b-vlm-weld-explainability-lora && \
deactivate && \
cd ../..
```

## Deploy the vLLM Service

Run:

```bash
 cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
 make up_vllm
```

For a fresh build before deployment:

```bash
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
make build
make up_vllm
```

## Verify the Deployment

1. Check overall stack health:

   > **Note:** The command `make status` may show errors in containers like ia-grafana when the user has not logged in
   > for the first login OR due to session timeout. Just login again in Grafana and functionality wise if things are working, then
   > ignore `user token not found` errors along with other minor errors which may show up in Grafana logs.

   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
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
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
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