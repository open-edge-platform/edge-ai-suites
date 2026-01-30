# Get Started

This guide covers the rapid deployment of the Live Video Alert system using Docker.

## Prerequisites

- Docker and Docker Compose
- Intel® hardware (optional but recommended for OpenVINO performance)
- **OpenVINO Model Server (OVMS) with VLM support**: Must be running before deploying this application. Follow the [OVMS VLM deployment guide](https://docs.openvino.ai/2025/model-server/ovms_demos_continuous_batching_vlm.html#fast-deployment-with-openvino-models-pulled-directly-from-huggingface-hub)

## Initial Setup

1. **Clone the repository**:
     ```bash
     # Clone the latest on mainline
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
     # Alternatively, clone a specific release branch
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites -b <release-tag>
     ```
    Note: Adjust the repo link appropriately in case of forked repo.

2. **Navigate to the Directory**:
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-alert
     ```

3. **Configure Image Registry and Tag**:
     ```bash
     export REGISTRY="intel/"
     export TAG="rc2026.1.3"
     ```
    Skip this step if you prefer to build the sample application from source. For detailed instructions, refer to [How to Build from Source](./how-to-build-source.md) guide for details.

4. **Configure Environment**:
   Create a `.env` file in the project root or set environment variables directly:
     ```bash
     # Required: Video stream source (RTSP URL or local file path)
     RTSP_URL=rtsp://<camera-ip>:<port>/stream
     
     # Required: VLM inference endpoint (must be running before deployment)
     VLM_URL=http://localhost:8000/v3
     
     # Optional: Model name for VLM service
     MODEL_NAME=Phi-3.5-Vision
     
     # Optional: Application port (default: 9000)
     PORT=9000
     ```
   
   Notes:
   - For local video files, use absolute paths: `RTSP_URL=/app/resources/your-video.mp4`
   - Ensure the VLM service at `VLM_URL` is accessible before starting

5. **Start the Application**:
   Run the following command from the project root:

     ```bash
     docker compose up -d
     ```

6. **Verify Deployment**:
   Check that the container is running:
     ```bash
     docker ps
     ```
   
   View logs to ensure successful startup:
     ```bash
     docker logs agentic-nvr
     ```

7. **Access the Dashboard**:
   Open your browser and navigate to:
     ```
     http://localhost:9000
     ```
   (Replace `localhost` with your server IP if accessing remotely)

## Using the Application

### Adding Video Streams
1. In the sidebar under **Stream Configuration**, enter:
   - **Stream Name**: A descriptive name (e.g., "Lobby Camera")
   - **RTSP URL**: Your camera's RTSP stream URL
2. Click **Add New Stream**

### Configuring Alerts
1. Under **AI Agent Alerts** section:
   - Click **Create New Alert** (up to 4 alerts supported)
   - Enter an **Alert Name** (e.g., "Person Detection")
   - Write a **Prompt** describing the condition (e.g., "Is there a person?")
2. Click **Save** to apply changes
3. Results will appear in real-time on the video cards

### Monitoring Results
- Each video card shows the live stream with analysis results below
- Use the dropdown to filter alerts: "All Alerts" or individual alert types
- Results update automatically via Server-Sent Events (SSE)

## Stopping the Application

To stop all services:
```bash
docker compose down
```
