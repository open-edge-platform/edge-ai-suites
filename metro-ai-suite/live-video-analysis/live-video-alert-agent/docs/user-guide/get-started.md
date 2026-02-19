# Get Started

This guide covers the rapid deployment of the Live Video Alert Agent system using Docker.

## Prerequisites

- Docker and Docker Compose
- Internet connection (for initial VLM model download)

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
     export TAG="latest"
     ```
    Skip this step if you prefer to build the sample application from source. For detailed instructions, refer to [How to Build from Source](./how-to-build-source.md) guide for details.

4. **Configure Environment**:
   
   **Optional environment variables:**
   ```bash
   # Optional: Pre-configure a video stream (can also add streams via UI)
   export RTSP_URL=rtsp://<camera-ip>:<port>/stream
   
   # Use a different VLM model (default: Phi-3.5-vision-instruct-int4-ov)
   # Example: Use InternVL2-2B model instead
   export OVMS_SOURCE_MODEL=OpenVINO/InternVL2-2B-int4-ov
   export MODEL_NAME=InternVL2-2B
   
   # Change application port (default: 9000)
   export PORT=9001
   
   # Enable debug logging
   export LOG_LEVEL=DEBUG
   ```
   
   **Note:** All environment variables are optional. Streams can be added dynamically through the web UI after startup.

5. **Start the Application**:
   Run the following command from the project root:

     ```bash
     docker compose up -d
     ```
   
   **Note:** 
   - First run downloads the VLM model (~2GB, 5-10 minutes)
   - An init container runs briefly to set up volume permissions.
   - Subsequent runs start instantly

6. **Verify Deployment**:
   Check that containers are running:
     ```bash
     docker ps
     ```
   
   View application logs:
     ```bash
     docker logs agentic-nvr
     ```

6. **Access the Dashboard**:
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
2. Click **Save** to activate

### Viewing Results
- The dashboard shows the live stream with analysis results below
- Use the dropdown to filter alerts: "All Alerts" or individual alert types
- Results update automatically via Server-Sent Events (SSE)

## Managing the Application

### Stopping Services

To stop all services:
```bash
docker compose down
```

### Restarting After Changes

```bash
# Restart both services
docker compose restart

# Restart only the application (VLM service keeps running)
docker compose restart agentic-nvr
```

### Viewing Logs

```bash
# Follow all logs
docker compose logs -f

# VLM service logs
docker logs -f ovms-vlm

# Application logs
docker logs -f agentic-nvr
```

### Clearing Model Cache

If you need to re-download the model or switch models:
```bash
# Remove everything including model cache
docker compose down -v

# Set environment and start fresh
export RTSP_URL=rtsp://<camera-ip>:<port>/stream
docker compose up -d
```

## Troubleshooting

### Permission Issues

**Problem**: OVMS fails with "permission denied" on `/models`.

**Solution**: An init container (`ovms-init`) automatically sets permissions. It will show as `Exited (0)` - this is normal.

**Verify**:
```bash
docker ps -a --filter "name=ovms-init"  # Should show: Exited (0)
docker exec ovms-vlm ls -lah /models    # Should be owned by ovms
```

### Other Issues

```bash
# Check status
docker compose ps

# View logs
docker compose logs -f

# Clean restart
docker compose down -v
export RTSP_URL=<your-url>
docker compose up -d
```
