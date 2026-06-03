# Quick Start: Live Video Captioning

Get the application up and running with USB/webcam in 5 steps!

Live Video Captioning uses VLM to automatically describe what is happening in a live video stream — from a camera or an RTSP feed — and displays those descriptions in real time on a web dashboard.

Note:
1. The time taken is a function of network bandwidth. Model and image download time will determine how fast the user is up and running with the application.
2. If there is no USB/webcam device attached, user can configure a test RTSP stream following [these](./get-started/simulated-rtsp-stream-guide.md) instructions.

---

## Before You Begin

Make sure your machine meets these minimums:

| What | Minimum |
|------|---------|
| Processor | Intel® Core™ Ultra (2nd or 3rd gen) with integrated GPU |
| Memory | Min 16 GB RAM |
| Disk | 64 GB free SSD space |
| OS | Ubuntu 24.04 or 24.10 |
| Internet | Required for first-time setup |

You also need **Docker** installed. If you do not have it yet, run the following two commands in a terminal:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

> After running those commands, **log out and log back in** for the changes to take effect.

---

## Step 1 — Get the Code

Open a terminal and run:

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/live-video-captioning
```

---

## Step 2 — Set Up Configuration

Run the setup script — it automatically detects your machine's IP address and prepares the configuration file:

```bash
bash scripts/setup_env.sh
```

---

## Step 3 — Download the AI Model (one-time, ~5 min)

```bash
./model_download_scripts/download_models.sh \
  --model OpenGVLab/InternVL2-1B \
  --type vlm \
  --weight-format int8
```

This downloads the AI model that powers the captions. It only needs to run once. The model parameter is configurable and the user is requested to confirm the license agreement before the download.

---

## Step 4 — Start the Application

```bash
docker compose up -d
```

Docker pulls the required containers and starts all services in the background. The first run may take a few minutes to download images.

---

## Step 5 — Open the Dashboard

Once the services are running, open a web browser and go to:

```
http://<YOUR_IP>:4173
```

Replace `<YOUR_IP>` with the IP address shown at the end of Step 2, or find it by running `hostname -I` in the terminal.

### Using the Dashboard

1. **Enter your video source** — paste an RTSP camera URL (for example `rtsp://192.168.1.10/stream`) or select the USB/webcam device in case it is available.
2. **Select a model** — choose from the available AI models in the drop-down list.
3. **Click Start** — captions appear alongside the live video preview.

---

## Step 6 — Stop the Application

When you are done, stop all services with:

```bash
docker compose down
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Dashboard does not load | Wait 30 seconds after `docker compose up -d`, then refresh |
| No captions appear | Check that the RTSP URL is reachable from this machine |
| Stream behind a proxy | Add the camera's IP to `no_proxy` in your shell environment |
| "permission denied" with Docker | Run `sudo usermod -aG docker $USER`, then log out and back in |
| "failed to resolve reference docker.io" with Docker | Docker daemon cannot reach Docker Hub over the network to download the microservices. This could be due to missing organization proxy configuration in docker setup. Follow [this](https://docs.docker.com/engine/daemon/proxy/) instruction to set it up. |
| Hardware-encoded camera not supported | This application does not supported hardware-encoded format webcam (for example, H.264). Use a compatible webcam that provides raw video output(for example, YUYV/MJPEG). |
---

## Next Steps

Once you are comfortable with the basics:

- [System Requirements](./get-started/system-requirements.md) — full hardware and software details
- [Get Started](./get-started.md) — complete setup guide with all configuration options
- [How It Works](./how-it-works.md) — understand the architecture behind the application
