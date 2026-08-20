# Quick Start: Live Video Captioning RAG

Get the application up and running in a few simple steps.

Live Video Captioning RAG works with Live Video Captioning to generate live captions from a video stream, store caption context in a vector database, and let you ask natural-language questions about what happened in the video.

> **Note:**
>
> 1. Setup and first run time depends on network speed because Docker images and models are downloaded.
> 2. If you do not have a camera stream, configure a simulated RTSP stream by following [these instructions](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/live-video-captioning/get-started/simulated-rtsp-stream-guide.html).

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

> After running those commands, **log out and log back in** for the changes to take effect.

---

## Step 1 - Get the Code

Open a terminal and run:

```bash
git clone --filter=blob:none --sparse --branch release-2026.2.0 https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/live-video-captioning-rag
```

---

## Step 2 - Set Up Configuration

Run the setup script to create the `.env` file and auto-detect your host IP:

```bash
bash scripts/setup_env.sh
```

---

## Step 3 - Download AI Models (one-time)

You need two models:

1. A **VLM** model for Live Video Captioning.
2. An **LLM** model for RAG question-answering.

Run:

```bash
# VLM model for caption generation
./model_download_scripts/download_models.sh \
	--model OpenGVLab/InternVL2-1B \
	--type vlm \
	--weight-format int8

# LLM model for RAG responses
./model_download_scripts/download_models.sh \
	--model Qwen/Qwen2.5-3B-Instruct \
	--type llm \
	--device CPU \
	--weight-format int8
```

If a model is gated on Hugging Face, set your token first:

```bash
export HUGGINGFACEHUB_API_TOKEN=<your-token>
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

> **Note:** NPU support currently only works with `int4` quantization when converting VLM models. If `--device NPU` is specified alongside `int8` or `fp16`, the script will automatically switch the quantization to `int4`. Additionally, LLM model support for NPU is not yet available in Live-Video-Captioning-RAG.

---

## Step 4 - Start the Application

```bash
docker compose up -d
```

The first run may take a few minutes while images are downloaded and services become healthy.

---

## Step 5 - Open the Dashboards

1. Open Live Video Captioning at:

   ```text
   http://<YOUR_IP>:4173
   ```

2. In the Live Video Captioning dashboard:
   - Enter a video source (RTSP URL or USB/webcam if available).
   - Select the VLM device and model.
   - Click **Start** and confirm captions are appearing.

3. Open Live Video Captioning RAG via `chat icon` on the top right of Live Video Captioning dashboard or open a new tab with:

   ```text
   http://<YOUR_IP>:4172
   ```

4. Ask questions about the live or recent scene in the chat panel.

---

## Step 6 - Stop the Application

When you are done:

```bash
docker compose down
```

---

## Troubleshooting

| Problem                                            | What to try                                                                           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------- |
| RAG dashboard does not load                        | Wait 30-60 seconds after `docker compose up -d`, then refresh `http://<YOUR_IP>:4172` |
| Live captioning dashboard does not load            | Verify `http://<YOUR_IP>:4173` is reachable and containers are running (`docker ps`)  |
| No captions appear                                 | Check that your RTSP URL is reachable from this machine                               |
| No RAG answers/context                             | Ensure captioning is running first so embeddings can be ingested                      |
| Stream behind a proxy                              | Add the camera IP/host to `no_proxy` in your shell environment                        |
| "permission denied" with Docker                    | Run `sudo usermod -aG docker $USER`, then log out and back in                         |
| Model download fails with authentication error     | Set `HUGGINGFACEHUB_API_TOKEN` and rerun the command                                  |
| Model download interrupted or fails due to network | Remove model folders (`ov_models/`, `llm_models/`, `ovms_model/`) and rerun download  |

---

## Next Steps

After quick start setup, continue with:

- [System Requirements](./get-started/system-requirements.md) - full hardware and software details.
- [Get Started](./get-started.md) - a complete setup guide with advanced configuration.
- [How It Works](./how-it-works.md) - architecture and data flow.
