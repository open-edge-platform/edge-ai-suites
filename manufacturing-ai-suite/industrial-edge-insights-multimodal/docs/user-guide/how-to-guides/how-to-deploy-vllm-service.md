# Deploy the vLLM Service for Defect Explanation

This section shows how to deploy the multimodal sample application with the vLLM service
enabled using the Makefile targets.

## System Requirements

| Component        | Minimum Requirement                            |
| ---------------- | ---------------------------------------------- |
| Operating System | Ubuntu OS version 24.04 LTS or later           |
| Hardware         | Intel® Core™ Ultra Series 3 processor or newer |

## Prerequisites

1. Ensure the `.env` file is configured with valid values for:
   - `HOST_IP`
   - `INFLUXDB_USERNAME`, `INFLUXDB_PASSWORD`
   - `VISUALIZER_GRAFANA_USER`, `VISUALIZER_GRAFANA_PASSWORD`
   - `MTX_WEBRTCICESERVERS2_0_USERNAME`, `MTX_WEBRTCICESERVERS2_0_PASSWORD`
   - `S3_STORAGE_USERNAME`, `S3_STORAGE_PASSWORD`

## Download Models

This section shows how to download the `Unsloth Qwen3.5-2B` model and `Unsloth Qwen3.5-2B fine-tuned LoRA` adapter.

1. Review and accept the [Unsloth Qwen3.5-2B license](https://huggingface.co/unsloth/Qwen3.5-2B/blob/main/LICENSE) before downloading.

   > **Note:** The [Low-Rank Adaptation (LoRA) adapter](https://huggingface.co/Intel/qwen3.5-2b-vlm-weld-explainability-lora) was specifically trained on a subset of the [Intel Robotic Welding Multimodal Dataset](https://huggingface.co/datasets/IntelLabs/Intel_Robotic_Welding_Multimodal_Dataset) and may not generalize to generic weld datasets.

2. Download the model and adapter:

```bash
mkdir -p configs/vllm/huggingface configs/vllm/models && \
cd configs/vllm/ && \
rm -rf .modelenv && \
python3 -m venv .modelenv && \
source .modelenv/bin/activate && \
pip3 install huggingface_hub==1.23.0 && \
rm -rf huggingface models && \
hf download unsloth/Qwen3.5-2B \
    --local-dir ./huggingface/Qwen3.5-2B && \
hf download Intel/qwen3.5-2b-vlm-weld-explainability-lora \
    --local-dir ./models/qwen3.5-2b-vlm-weld-explainability-lora && \
deactivate && \
cd ../..
```

## Deploy the vLLM Service

> **Note:** vLLM preallocates GPU-addressable memory up to the limit specified by
> `VLLM_GPU_MEMORY_UTILIZATION` (VRAM on discrete GPU; shared system memory on integrated GPU).
> Since the optimal value varies between platforms, update `VLLM_GPU_MEMORY_UTILIZATION` in
> the `.env` file to match your target hardware.

1. Run the Makefile target:

   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
   make up_vllm
   ```

2. (Optional) To build from source instead of deploying the pre-built artifacts, run the
   following for a fresh build before deployment:

   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
   make build
   make up_vllm
   ```

## Verify the Deployment

1. Check the overall stack health:

   > **Note:** The command `make status` may show errors in containers like `ia-grafana` if
   > you have not logged in to the Grafana dashboard for the first time, or if your session has
   > timed out. Log in to the Grafana dashboard, and if the dashboard works correctly, ignore
   > `user token not found` and other minor errors in the Grafana logs.

   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
   make status
   ```

2. Confirm that the vLLM container is running:

   ```bash
   docker ps --filter "name=vllm-server"
   ```

3. Inspect vLLM logs:

   ```bash
   docker logs -f vllm-server
   ```

4. Check the output in Grafana dashboard:
   - Use the link `https://localhost:3000` to open the Grafana dashboard in a browser, preferably
     the Chrome browser. For Helm deployment, use the link `https://localhost:30001`.
   - Log in to the Grafana dashboard using the `VISUALIZER_GRAFANA_USER` and `VISUALIZER_GRAFANA_PASSWORD`
     values from the `.env` file:

     ![Grafana login](../_assets/login_wt.png)

   - After logging in, click **Dashboards**:
     ![Menu view](../_assets/dashboard.png)

   - Select **Multimodal Weld Defect Detection Explainability Dashboard**:
     ![Multimodal Weld Defect Detection Explainability Dashboard](../_assets/grafana_dashboard_selection_vllm.png)

   - The following appears:

     ![vLLM Reasoning for weld data](../_assets/vllm_response.png)

## Stop the Deployment

To bring down the full stack:

```bash
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal
make down
```

## Troubleshooting

- `vllm-server` startup delay after deployment
  The `vllm-server` service can take about 10 minutes to fully come up after `make up_vllm`.
  This is expected as the model initializes and loads into memory.

- `Error: configs/vllm/models directory does not exist.`
  Create the directory and place the required model artifacts in it.

- `Error: configs/vllm/models directory is empty.`
  Add model files and checkpoints before running `make up_vllm`.

- `HOST_IP is not set` or `HOST_IP is not a valid IPv4 address format.`
  Update `HOST_IP` in `.env` with a valid IPv4 address.

- Username and password validation failures from `check_env_variables`
  Update `.env` values so they match the Makefile validation rules.
