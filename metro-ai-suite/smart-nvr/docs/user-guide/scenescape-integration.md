# Integrate Scenescape with Smart NVR

This guide describes how to integrate Intel® SceneScape with Smart NVR for enhanced traffic monitoring using live data from the Smart Intersection application.

## Overview

Smart NVR integrates with Intel® SceneScape to enable:

- Real-time object counting and tracking (vehicles, pedestrians)
- Traffic flow analysis
- Automated event routing based on count thresholds
- Enhanced surveillance for smart intersection management

## Prerequisites

- Docker and Docker Compose installed
- The `edge-ai-suites` repository cloned with the `metro-vision-ai-app-recipe` directory adjacent to `smart-nvr`

## Deployment Modes

Smart NVR with SceneScape supports two deployment modes:

| Mode | Description | Command |
|------|-------------|---------|
| **Single-Node** | All services (SI + NVR) on one machine | `source setup.sh start` |
| **Distributed Node** | SI on System 1, NVR on System 2 | `source setup.sh start-si` / `source setup.sh start-nvr` |

## Single-Node Deployment

In single-node mode, all services run on one machine. The setup script performs the following steps automatically:

1. Validates required environment variables
2. Configures DL Streamer and Frigate for SceneScape mode
3. Downloads demo videos and starts the MediaMTX RTSP streamer
4. Starts the Smart Intersection stack (runs `install.sh` on first launch)
5. Starts the NVR stack and connects it to the SceneScape network

### Set Environment Variables

```bash
export NVR_SCENESCAPE=true
export VSS_SUMMARY_IP=<vss_ip>
export VSS_SUMMARY_PORT=<vss_port>
export VSS_SEARCH_IP=<vss_ip>
export VSS_SEARCH_PORT=<vss_port>
# export RTSP_STREAM_PORT=<rtsp port>      # optional, default 8554
# export MQTT_USER=<mqtt-username>         # optional, auto-generated if omitted
# export MQTT_PASSWORD=<mqtt-password>     # optional, auto-generated if omitted
```

### Start

```bash
source setup.sh start
```

### Verify

```bash
docker logs nvr-event-router -f
# Expected output: "SceneScape MQTT client started"
```

The UI is available at `http://<host_ip>:7860`.

## Distributed Node Deployment

In distributed mode, Smart Intersection runs on a dedicated machine (System 1) while the NVR stack runs on a separate machine (System 2).

### System 1 (SI Node)

```bash
export NVR_SCENESCAPE=true
# export RTSP_STREAM_PORT=<rtsp port>         # optional, default 8554
# export RTSP_STREAM_HOST=<external_rtsp_ip>  # optional: set to use an external RTSP source; skips local demo streamer
source setup.sh start-si
```

By default, `start-si` downloads demo videos and starts a local MediaMTX RTSP streamer. If `RTSP_STREAM_HOST` is set to a different machine's IP, the local streamer is skipped and SI reads from the external RTSP source instead.

Upon successful startup, the script outputs the System 1 IP address required for System 2 configuration.

### System 2 (NVR Node)

```bash
# Required
export NVR_SCENESCAPE=true
export SCENESCAPE_MQTT_BROKER=<system1_ip>
export RTSP_STREAM_HOST=<system1_ip>
export VSS_SUMMARY_IP=<vss_ip>
export VSS_SUMMARY_PORT=<vss_port>
export VSS_SEARCH_IP=<vss_ip>
export VSS_SEARCH_PORT=<vss_port>
# Optional 
# export RTSP_STREAM_PORT=<rtsp port>      # default 8554
# export MQTT_USER=<mqtt-username>         # optional, auto-generated if omitted
# export MQTT_PASSWORD=<mqtt-password>     # optional, auto-generated if omitted
source setup.sh start-nvr
```

System 2 connects to System 1's MQTT broker (port `1883` by default) for SceneScape events and RTSP server (port `8554` by default) for video streams.

## Stop Services

```bash
# Single-node
source setup.sh stop

# Distributed node
source setup.sh stop-nvr  # System 2
source setup.sh stop-si   # System 1

# Restart
source setup.sh restart
```

When stopping System 1, if a local RTSP streamer is running, the script prompts:

```text
Local RTSP streamer is running. Stop it too? [y/N]
```

- Enter `y` to stop both SI services and the RTSP streamer.
- Enter `n` or press Enter to stop only SI services and leave the streamer running.
  The streamer can be stopped independently with `source setup.sh stop-streamer`.

### RTSP Streamer Only

To start only the MediaMTX RTSP streamer without launching the full NVR or Smart Intersection stack, use the following command. This is intended for development and testing scenarios where video stream availability needs to be verified independently.

```bash
source setup.sh start-streamer
```

To stop the streamer:

```bash
source setup.sh stop-streamer
```

## Verify Integration

```bash
docker logs nvr-event-router -f
# Expected output: "SceneScape MQTT client started"
```

## User Interface

### With Intel® SceneScape Enabled

![SceneScape Enabled Interface](./_assets/Scenescape_enabled.png)

When Intel® SceneScape is enabled (`NVR_SCENESCAPE=true`):

- Source dropdown shows only **"scenescape"** (Frigate source is not available in this mode)
- **Count** field is visible and editable
- Minimum count threshold for rule triggering can be configured (e.g., 5, 10, 15)
- Rules table includes a "Count" column for tracking thresholds
- Count validation enforces non-negative integers

## Auto-Route Events Configuration

### Creating Rules

1. Navigate to the **Auto-Route Events** tab
2. **Source** is pre-set to "scenescape"
3. **Set Count:** Define the minimum detection threshold (e.g., 5)
4. **Select Camera:** Choose the target camera
5. **Choose Detection Label:** Select the object type ("vehicle" or "pedestrian")
6. **Select Action:** Choose "Summarize" or "Add to Search"
7. Click **Add Rule**

### Rule Behavior Example

```text
Source: scenescape
Camera: camera1
Count: 5
Label: vehicle
Action: Summarize
```

This rule triggers video summarization when 5 or more vehicles are detected in camera1.

## Troubleshooting

**SceneScape features not visible in UI**

Verify that `NVR_SCENESCAPE` is set to `true` and restart the services:

```bash
echo $NVR_SCENESCAPE
export NVR_SCENESCAPE=true
source setup.sh restart
```

After restarting, perform a hard refresh in the browser (`Ctrl+Shift+R` or `Cmd+Shift+R`).

**No SceneScape events received**

```bash
# Check MQTT connectivity to the SceneScape broker
docker logs nvr-event-router | grep -i scenescape

# Verify Smart Intersection containers are running
docker ps | grep metro-vision-ai-app-recipe
```

**Diagnostic commands**

```bash
# Monitor live SceneScape MQTT messages
docker logs nvr-event-router -f | grep "scenescape"

# List all running containers with status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check container resource utilization
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

## Support

When reporting issues, verify the following:

1. **Environment variables** — Confirm all required variables are exported: `env | grep -E "NVR_|SCENESCAPE|MQTT|VSS"`
2. **MQTT connectivity** — Check logs for the message: `"SceneScape MQTT client started"`
3. **Smart Intersection** — Confirm SI containers are running: `docker ps | grep metro`
4. **Distributed node connectivity** — Confirm System 2 can reach System 1 on port 1883 (MQTT) and port 8554 (RTSP)
5. **Resource utilization** — Run `docker stats --no-stream` to identify resource-constrained containers

For general Smart NVR issues, refer to the [Troubleshooting Guide](./troubleshooting.md).
