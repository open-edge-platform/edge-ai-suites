# Quick Start: Real Time Scene Understanding

Get the application up and running with RTSP streams in a few simple steps.

Real Time Scene Understanding works by analyzing live video streams and providing scene understanding in real time and provide temporal-based understanding on consecutive frames, all by leveraging the power of Vision Language Models (VLMs).

> **Note:**
>
> 1. The time taken is a function of network bandwidth. Model and image download time will determine how fast the user is up and running with the application.
> 2. If there is no USB/webcam device attached, user can configure a test RTSP stream following [these instructions](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-video-captioning/get-started/simulated-rtsp-stream-guide.html).

---

## Before You Begin

Make sure your machine meets these minimums:

| What      | Minimum                                                      |
| --------- | ------------------------------------------------------------ |
| Processor | Intel(R) Core(TM) Ultra (2nd or 3rd gen) with integrated GPU |
| Memory    | Min 16 GB RAM                                                |
| Disk      | 64 GB free SSD space                                         |
| OS        | Ubuntu 24.04 or 24.10                                        |
| Internet  | Required for first-time setup                                |

You also need **Docker** installed. If you do not have it yet, run the following two commands in a terminal:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

> After running those commands, **log out and log back in** to apply the Docker group changes.

---

## Step 1 - Get the Code

Open a terminal and run:

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/real-time-scene-understanding
```

---

## Step 2 - Set Up Configuration

Run the setup script to create the `.env` file - it automatically detects your machine's IP address and prepare the necessary configuration.

```bash
bash scripts/setup_env.sh
```

## Step 3 - Download AI Models (one-time)

You need two Vision Language Models (VLMs) for real-time scene understanding:

1. **ALERT_VLM_MODEL** - Used for initial single-frame based scene understanding.
2. **DEEP_ANALYZER_MODEL** - Used for temporal-based understanding on consecutive frames.

### Setting Hugging Face Token

If a model is gated on Hugging Face, set your token first:

```bash
export HUGGINGFACEHUB_API_TOKEN="your-token"
```

### Specifying the conversion device

By default, conversion runs on CPU. To target another device:

```bash
./model_download_scripts/download_models.sh \
	--model <model_name> \
	--type <vlm|llm> \
	--weight-format int8 \
	--device <CPU|GPU|NPU>
```

> **Note:** NPU support currently only works with `int4` quantization when converting VLM models. If `--device NPU` is specified alongside `int8` or `fp16`, the script will automatically switch the quantization to `int4`.
> **Note**: NPU compatibility varies by model. Before selecting a model, confirm NPU support in [OpenVINO Supported Models](https://docs.openvino.ai/2026/documentation/compatibility-and-support/supported-models.html).

### Downloading the Models

Run:

```bash
# Download "ALERT_VLM_MODEL" for single-frame based scene understanding
./model_download_scripts/download_models.sh \
	--model Qwen/Qwen3-VL-2B-Instruct \
	--type vlm \
	--weight-format int4 \
	--device CPU

# Download "DEEP_ANALYZER_MODEL" for temporal-based understanding on consecutive frames
./model_download_scripts/download_models.sh \
	--model Qwen/Qwen3-VL-8B-Instruct \
	--type vlm \
	--weight-format int4 \
	--device GPU
```

> Note: `DEEP_ANALYZER_MODEL` must support video input because deep analysis relies on temporal understanding across consecutive frames. Support is model-specific in OpenVINO GenAI: some VLMs are image-only. Before choosing a model, verify it in the official [Supported Models (VLM)](https://openvinotoolkit.github.io/openvino.genai/docs/supported-models/#vision-language-models-vlms) page and review [Visual Processing Using VLMs](https://openvinotoolkit.github.io/openvino.genai/docs/use-cases/visual-processing/) for image/video input behavior.

The downloaded model names and devices must match the settings in `.env`. For the two example downloads above, set:

```dotenv
ALERT_VLM_MODEL=Qwen3-VL-2B-Instruct
ALERT_VLM_DEVICE=CPU
DEEP_ANALYZER_MODEL=Qwen3-VL-8B-Instruct
DEEP_ANALYZER_DEVICE=GPU
```

These model names and devices match the setup template. Model files must be under `ov_models/<device-lowercase>/<model-name>/`.

---

## Step 4 - Start the Application

```bash
docker compose up -d
```

The first run may take a few minutes while images are downloaded and services become healthy.

You can check the status of the services with:

```bash
docker compose ps
```

---

## Step 5 - Open the Dashboard

Once the services are ready, open the Real Time Scene Understanding dashboard at:

```text
http://<YOUR_IP>:9100
```

### Using the Dashboard

- Enter a video source (RTSP URL).
- Enter the alert prompt and the deep-analysis prompt.
- Click "Start" to begin the pipeline.

---

## Step 6 - Stop the Application

To stop the application, run:

```bash
docker compose down
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Dashboard does not load | Wait 30 seconds after `docker compose up -d`, then refresh the page. If still unavailable, run `docker compose ps` and confirm services are in `Up` state. |
| Deep analyzer fails with **"Video preprocessing isn't implemented for this model"** | The selected `DEEP_ANALYZER_MODEL` does not support video input in OpenVINO GenAI. Choose a video-capable VLM and verify support in [Supported Models (VLM)](https://openvinotoolkit.github.io/openvino.genai/docs/supported-models/#vision-language-models-vlms) and [Visual Processing Using VLMs](https://openvinotoolkit.github.io/openvino.genai/docs/use-cases/visual-processing/). |
| Stream is behind a proxy | Add the RTSP stream host or IP to `no_proxy` and retry. Example: `export no_proxy=$no_proxy,<rtsp_host_or_ip>`. |
| "permission denied" with Docker | Run `sudo usermod -aG docker $USER`, log out, then log back in and rerun the command. |
| Model download fails with authentication error | Set `HUGGINGFACEHUB_API_TOKEN` with a valid token, then rerun the model download command. |
| Model download interrupted or fails due to network | Remove `ovms_model` and the affected model directory under `ov_models/`, then rerun the download command. |

---

## Next Steps

Once you are familiar with the basic usage of the application, you can explore the following next steps:

- [System Requirements](./get-started/system-requirements.md) - full hardware and software requirements for running the application.
- [Get Started](./get-started.md) - a more complete and detailed setup guide with all configuration options to get the application up and running.
- [How It Works](./how-it-works.md) - an overview of the application's architecture and workflow.