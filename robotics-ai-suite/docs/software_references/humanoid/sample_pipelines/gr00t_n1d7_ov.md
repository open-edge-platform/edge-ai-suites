# gr00t-n1.7

Isaac-GR00T is NVIDIA's embodied AI foundation-model stack for robot manipulation and generalist control. It is designed for workflows involving perception, reasoning, and action generation in robotics applications.

![Isaac-GR00T](https://raw.githubusercontent.com/NVIDIA/Isaac-GR00T/main/media/header_compress.png)\
*Figure source: <https://github.com/NVIDIA/Isaac-GR00T>*

This project demonstrates an implementation the gr00t n1.7 using the OpenVINO toolkit, specifically accelerating inference on Intel platforms. It provides a comprehensive end-to-end pipeline.

## Installation

This project extends the open-source project [isaac-gr00t](https://github.com/NVIDIA/Isaac-GR00T) to provide OpenVINO acceleration features on Intel compute platforms. Get [the source code](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/pipelines/gr00t-n1d7-ov) from the Open Edge Platform repo. To set up the environment, you need to initialize and patch the submodule:

```bash
git submodule update --init --recursive isaac-gr00t
cd isaac-gr00t
```
Apply the patches:
```bash
git am --whitespace=fix ../patches/*.patch
```

### Setup Python Environment

Install the packages as prerequisites:
```bash
sudo apt install -y libegl1-mesa-dev libglu1-mesa

```

If you would like to use `uv`, you can set up the environment and install dependencies by running:
```bash
uv sync --all-extras
```

> Follow the [guide](https://docs.astral.sh/uv/getting-started/installation/) to install uv.
> You can run a Python file by using:
> `uv run --all-extras <your_python_file>`.

Alternatively, you can create a Python environment:
```bash
python3 -m venv gr00t_env
source pi_env/bin/activate
pip install -e . --extra-index https://download.pytorch.org/whl/cpu
```

## Model Preparation

Running model inference with the OpenVINO toolkit requires converting the model to the OpenVINO IR format.
You can download the finetuned checkpoint form HF on a simulation task for convenience.

```bash
uv run hf download nvidia/GR00T-N1.7-LIBERO \
  --include "libero_10/config.json" "libero_10/embodiment_id.json" \
            "libero_10/model-*.safetensors" "libero_10/model.safetensors.index.json" \
            "libero_10/processor_config.json" "libero_10/statistics.json" \
  --local-dir checkpoints/GR00T-N1.7-LIBERO
```

Alternatively, you can convert your own checkpoints trained using the Gr00t framework.

### Convert Gr00t n1.7 model

To convert the standard Gr00t n1.7 model to OpenVINO single-IR, use the `export_ov_n1d7_single_ov.py` script.

**Arguments:**

- `--model-path`: local checkpoint directory to export from
- `--dataset-path`: optional; use a real sample source to capture representative input shapes, or omit it to use dummy capture mode
- `--embodiment-tag`: embodiment configuration to load from the checkpoint and sample
- `--output-dir`: directory where the merged IR, metadata, and copied checkpoint config files are written
- `--precision fp16`: save the exported OpenVINO weights with fp16 compression
- `--device`: optional; defaults to `cpu`; this script also falls back to CPU for OV verification if the requested OV device is unavailable
- `--llm-lang-tokens`: optional; reserve 64 language-token slots here for static-sequence export, or omit it to bake in the captured sequence length

> **Notice**: Using the Gr00t n1.7 model in LeRobot will automatically download the [nvidia/Cosmos-Reason2-2B](https://huggingface.co/nvidia/Cosmos-Reason2-2B) from Hugging Face. Due to author restrictions, downloading the model requires logging into your Hugging Face account.
> If you encounter download errors, follow the [instructions](https://huggingface.co/docs/huggingface_hub/quick-start#authentication) on how to log in and authorize your account.

Examples (`uv`):

```bash
uv run python scripts/deployment/export_ov_n1d7_single_ov.py \
  --model-path checkpoints/GR00T-N1.7-LIBERO/libero_10/ \
  --dataset-path demo_data/libero_demo/ \
  --embodiment-tag LIBERO_PANDA \
  --output-dir ~/openvino_models/libero_single_direct_ov_optimal \
  --precision fp16 \
  --llm-lang-tokens 64
```

To convert the standard Gr00t n1.7 model to Osplit-component OpenVINO, use the `export_ov_n1d7.py` script.

**Arguments:**

- `--model-path`: local checkpoint directory to export from
- `--dataset-path`: optional; use a real sample source to capture representative input shapes, or omit it to use dummy capture mode
- `--embodiment-tag`: embodiment configuration to load from the checkpoint and sample
- `--output-dir`: directory where the exported component IR files, metadata, and copied checkpoint config files are written
- `--export-mode full_pipeline`: export ViT + LLM + VL self-attention + action head
- `--use-fused-dit`: optional; export the fused denoising loop instead of a separate DiT IR when supported
- `--precision fp16`: save the exported OpenVINO weights with fp16 compression
- `--device`: optional; defaults to `cpu`, or set it to `cuda` when you want export-time PyTorch execution on GPU
- `--llm-lang-tokens`: optional; reserve 64 language-token slots here for static-sequence export, or omit it to bake in the captured sequence length

Examples (`uv`):

```bash
uv run python scripts/deployment/export_ov_n1d7.py \
  --model-path checkpoints/GR00T-N1.7-LIBERO/libero_10/ \
  --dataset-path demo_data/libero_demo/ \
  --embodiment-tag LIBERO_PANDA \
  --output-dir ~/openvino_models/libero_full_direct_optimal \
  --export-mode full_pipeline \
  --use-fused-dit \
  --precision fp16 \
  --llm-lang-tokens 64
```

## Run Pipeline

### Inference Benchmarking

Run the `run_base_single_ov_inference.py` script to benchmark the single-OV policy inference pipeline, which includes preprocessing, model inference, and postprocessing.

```bash
uv run python scripts/deployment/run_base_single_ov_inference.py \
  --ov-model-dir ~/openvino_models/libero_single_direct_ov_optimal \
  --embodiment-tag LIBERO_PANDA \
  --num-samples 10 \
  --device GPU \
  --static-shape
```

**Arguments:**

- `--ov-model-dir`: directory containing exactly one merged single-OV XML model
- `--embodiment-tag LIBERO_PANDA`: embodiment configuration to use for dummy input generation and inference
- `--num-samples`: optional; number of timed inference iterations, default `10`
- `--device GPU`: run OpenVINO inference on the GPU plugin
- `--static-shape`: optional; reshape the single OpenVINO model to the actual input shapes before compilation

Run the `run_base_ov_inference.py` script to benchmark the multi-component full policy inference pipeline, which includes preprocessing, model inference, and postprocessing.

```bash
uv run python scripts/deployment/run_base_ov_inference.py \
  --ov-model-dir ~/openvino_models/libero_full_direct_optimal \
  --embodiment-tag LIBERO_PANDA \
  --num-samples 10 \
  --device GPU \
  --static-shape \
  --use-fused-dit \
  --full-ov
```

**Arguments:**

- `--ov-model-dir`: directory containing the exported multi-component OpenVINO IR files
- `--embodiment-tag LIBERO_PANDA`: embodiment configuration to use for dummy input generation and inference
- `--num-samples 10`: run 10 timed inference iterations
- `--device GPU`: run OpenVINO inference on the GPU plugin
- `--static-shape`: optional; reshape each OV component to static shapes captured from the first inference call before compilation
- `--use-fused-dit`: optional; use the fused DiT IR when `dit_fused_*.xml` is present. If it is missing, the runtime falls back to the non-fused 3-component action-head path when those files are available
- `--full-ov`: enable the full OpenVINO path for ViT, LLM, VL self-attention, and action head
