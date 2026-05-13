# Get Started

This guide covers the rapid deployment of the Live Video Alert Agent system using Docker.

## Prerequisites

- Docker and Docker Compose v2.20.2 or later
- Internet connection (for initial VLM model download)

## Initial Setup

1. Clone the suite:

2. **Navigate to the Directory**:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-alert-agent
     ```

   ```bash
   git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/live-video-analysis/live-video-alert-agent
   ```

2. Configure Image Registry and Tag:

   ```bash
   export REGISTRY="intel/"
   export TAG="latest"
   export HF_TOKEN=<your-huggingface-token>
   ```

   Skip this step if you prefer to build the sample application from source. For detailed instructions, refer to [How to Build from Source](./get-started/build-from-source.md) guide for details.

3. Configure the Environment:

   Optional environment variables:

   ```bash
   # Pre-configure a video stream
   export RTSP_URL=rtsp://<camera-ip>:<port>/stream

   # VLM model selection 
   export OVMS_SOURCE_MODEL=<vlm-model-name>   #Example: Openvino/Phi-3.5-vision-instruct-int4-ov

   # Log verbosity
   export LOG_LEVEL=DEBUG
   ```

   **Agentic dispatch — choose one mode:**

   *Option A — Google ADK with local OVMS (default, fully offline):*

   ```bash
   export USE_ADK=true
   export COMPOSE_PROFILES=adk-llm
   export LLM_MODEL=<llm-model-name>   #Example: Openvino/Phi-4-mini-instruct-int4-ov
   ```

   *Option B — Rule-based (no LLM needed):*

   ```bash
   export USE_ADK=false
   export COMPOSE_PROFILES=[]
   ```

   **Action tools** (configure the ones you want active):

   ```bash
   # Webhook (receives HMAC-signed POST)
   export WEBHOOK_URL=https://hooks.example.com/alert
   export WEBHOOK_SECRET=<hmac-secret>          # optional

   # MQTT
   export MQTT_BROKER=192.168.1.20
   export MQTT_PORT=1883
   export MQTT_USERNAME=<username>              # optional
   export MQTT_PASSWORD=<password>              # optional
   export MQTT_BASE_TOPIC=alerts/live-video
   ```

   **MCP (Model Context Protocol) — optional external tool servers:**

   ```bash
   export MCP_ENABLED=true                      # default: true
   export MCP_CONFIG_FILE=resources/mcp_servers.json  # path to MCP server config
   ```

   Configure MCP servers in `resources/mcp_servers.json`. See [API Reference](./api-reference.md#mcp) for details.

4. Start the Application:
   Run the following command from the project root:

   ```bash
   docker compose up -d
   ```

   **Note:**
   - First run downloads the VLM model (~2GB, 5-10 minutes)
   - An init container runs briefly to set up volume permissions.
   - Subsequent runs start instantly

5. Verify Deployment:
   Check that containers are running:

   ```bash
   docker ps
   ```

   View application logs:

   ```bash
   docker logs live-video-alert-agent
   ```

6. Access the Dashboard:
   Open your browser and navigate to `http://localhost:9000` (Replace `localhost` with your
   server IP if accessing remotely).

## Using the Application

### Adding Video Streams

1. In the sidebar under **Stream Configuration**, enter:
   - **Stream Name**: A descriptive name (e.g., "Lobby Camera")
   - **RTSP URL**: Your camera's RTSP stream URL
2. Click **Add New Stream**

### Configuring Alerts

1. Under **AI Agent Alerts** section:
   - Click **Create New Alert**
   - Enter an **Alert Name** (e.g., "Fire Detection")
   - Write a **Prompt** describing the condition (e.g., "Is there fire or smoke?")
   - Set the **Tools** to invoke on detection
2. Click **Save** to activate

   Alternatively, configure alerts via the REST API:

   ```bash
   curl -X POST http://localhost:9000/config/alerts \
     -H "Content-Type: application/json" \
     -d '[
       {
         "name": "Fire Detection",
         "prompt": "Is there fire or smoke visible?",
         "enabled": true,
         "severity": "critical",
         "tools": ["log_alert", "capture_snapshot"],
         "escalation": {
           "threshold_consecutive": 3,
           "additional_tools": ["trigger_webhook", "publish_mqtt"]
         }
       }
     ]'
   ```

### Viewing Results

- The dashboard shows the live stream with analysis results below
- Use the dropdown to filter alerts: "All Alerts" or individual alert types
- Results update automatically via Server-Sent Events (SSE)
- The `alert_action` event surface shows which tools were invoked and whether escalation occurred

### Checking Health and Metrics

```bash
# Liveness
curl http://localhost:9000/health

# Readiness (non-200 = not ready)
curl http://localhost:9000/ready

# System + per-stream metrics
curl http://localhost:9000/metrics

# List configured action tools
curl http://localhost:9000/tools
```

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
docker compose restart live-video-alert-agent
```

### Viewing Logs

```bash
# Follow all logs
docker compose logs -f

# VLM service logs
docker logs -f ovms-vlm

# Application logs
docker logs -f live-video-alert-agent
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

## Learn More

- [Build from Source](./get-started/build-from-source.md)
- [Deploy with Helm](./get-started/deploy-with-helm.md) - Deploy the application on Kubernetes with the bundled Helm chart.

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements
./get-started/build-from-source
./get-started/deploy-with-helm

:::
hide_directive-->
