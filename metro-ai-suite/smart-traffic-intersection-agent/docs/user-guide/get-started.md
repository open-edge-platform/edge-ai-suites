# Get Started

The **Scene Traffic Intersection Agent (STIA)** provides comprehensive traffic analysis capabilities including real-time intersection monitoring, directional traffic density analysis, and VLM-powered traffic insights. This guide provides step-by-step instructions to:

- Set up the agent using the automated setup script for quick deployment.
- Run predefined tasks to explore its functionality.
- Learn how to modify configurations to suit specific requirements.

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).
- **MQTT Broker**: Ensure access to an MQTT broker for traffic data streaming (or use the included broker).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

The Scene Traffic Intersection Agent includes an automated setup script that handles environment configuration, secrets generation, building, and deployment. This is the **recommended approach** for getting started.

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd metro-ai-suite/smart-traffic-intersection-agent/
```

### 2. Run the Complete Setup

The setup script provides several options. For a complete setup (recommended for first-time users):

```bash
# Complete setup: generates secrets, builds images, and starts all services
source setup.sh --setup
```

This single command will:

- Set all required environment variables with sensible defaults
- Generate required TLS certificates and authentication files
- Download demo video files for testing
- Build Docker images
- Start all services in the Scene Intelligence stack

The setup command starts all services including the containerized Traffic Intelligence agent.

### 3. Verify Services

Check that all services are running:

```bash
# Check container status
docker ps

# Verify Traffic Intelligence API
curl -s http://localhost:8081/health

# Verify Traffic Intelligence UI
curl -s http://localhost:7860/

# Check Scene Intelligence (if deployed separately)
curl -s http://localhost:8082/health
```

### 4. Access Services

The stack provides multiple interfaces:

- **Traffic Intelligence API**: `http://localhost:8081`
- **Traffic Intelligence UI**: `http://localhost:7860`
- **SceneScape Web**: `https://localhost:443`
- **API Documentation**: `http://localhost:8081/docs` (Swagger UI)

## Running Multiple Instances (Test/Dev Only)

For testing or development purposes, you may want to run multiple instances of the Smart Traffic Intersection Agent deployment to simulate multiple intersections. Each setup run (n runs) brings up n instances of the agent. In production environments, only a single ITT instance is required.

> **Note**: Step 2 (updating `intersection-config.json`) is optional for single-instance production deployments—the system runs with default values.

> **Recommendation**: Running 3 agent instances is recommended to experience all use cases and workflows. The number of instances you can run depends on available device resources—systems with higher resources can support more instances.

### 1. Clone the Repository

For each instance, clone the repository into a separate directory:

```bash
# First instance
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites-instance1
cd edge-ai-suites-instance1/metro-ai-suite/smart-traffic-intersection-agent/

# Second instance (in a new terminal)
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites-instance2
cd edge-ai-suites-instance2/metro-ai-suite/smart-traffic-intersection-agent/
```

### 2. Update intersection-config.json

Each instance must have a unique configuration. Edit `intersection-config.json` in each instance directory:

**Instance 1** (`edge-ai-suites-instance1/metro-ai-suite/smart-traffic-intersection-agent/intersection-config.json`):
```json
{
    "intersection-name": "intersection_1",
    "latitude": 33.3091336,
    "longitude": -111.9353095,
    "backend_port": "8081",
    "ui_port": "7860"
}
```

**Instance 2** (`edge-ai-suites-instance2/metro-ai-suite/smart-traffic-intersection-agent/intersection-config.json`):
```json
{
    "intersection-name": "intersection_2",
    "latitude": 33.4484,
    "longitude": -112.0740,
    "backend_port": "8082",
    "ui_port": "7861"
}
```

Ensure each instance has:
- A unique `intersection-name`
- Different `backend_port` and `ui_port` values to avoid port conflicts (optional—if not specified, an ephemeral port is picked automatically)

### 3. Run Setup for Each Instance

In each instance directory, run:

```bash
source setup.sh --setup
```

Each instance will deploy with its own configuration and ports.

## Manual Setup (Advanced Users)

For advanced users who need more control over the configuration, you can manually set up the stack using Docker Compose.

### Manual Environment Configuration

If you prefer to manually configure environment variables instead of using the setup script, see the [Environment Variables Guide](./environment-variables.md) for complete details. Key variables include:

```bash
# Core Scene Intelligence Configuration
export SCENE_INTELLIGENCE_PORT=8082
export LOG_LEVEL=INFO

# MQTT Broker Configuration
export MQTT_BROKER_HOST=broker.scenescape.intel.com
export MQTT_BROKER_PORT=1883
export MQTT_PORT=1883

# VLM Service Configuration
export VLM_BASE_URL=http://vlm-openvino-serving:8000
export VLM_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct
export VLM_SERVICE_PORT=9764

# SceneScape Configuration
export SCENESCAPE_PORT=443
export DLSTREAMER_PORT=8555

# Traffic Analysis Parameters
export HIGH_DENSITY_THRESHOLD=5.0
export VLM_WORKERS=4
export VLM_COOLDOWN_MINUTES=1
export VLM_TIMEOUT_SECONDS=10
```

## Testing the API

### 1. Traffic Intelligence Service

The Traffic Intelligence service provides real-time intersection monitoring:

```bash
# Check service health
curl -s http://localhost:8081/health

# Get current traffic data
curl -s http://localhost:8081/api/v1/traffic/current

# Get weather data
curl -s http://localhost:8081/api/v1/weather/current

```

### 2. Access UI Dashboard

Open the Traffic Intelligence UI in your browser:

Visit http://localhost:7860 in your browser


The UI provides:
- Real-time traffic visualization
- Camera image display
- Weather information
- VLM analysis results
- Traffic alerts and recommendations


## Service Ports

The complete stack exposes several services on different ports:

| Service | Port | Description |
|---------|------|-------------|
| Traffic Intelligence API | 8081 | Real-time traffic analysis REST API |
| Traffic Intelligence UI | 7860 | Interactive Gradio dashboard |
| Scene Intelligence API | 8082 | Scene analytics service (optional) |
| VLM OpenVINO Serving | 9764 | Vision Language Model service |
| SceneScape Web | 443 | Management web interface (HTTPS) |
| MQTT Broker | 1883 | Message broker |
| DL Streamer | 8555 | Video analytics pipeline |

## Configuration Files

The Scene Intelligence stack uses several configuration files located in the `config/` and `src/traffic-intelligence/config/` directories:

### Traffic Intelligence Configuration

The Traffic Intelligence service configuration is at `src/traffic-intelligence/config/traffic_intelligence.json`:

```json
{
  "intersection": {
    "id": "97781c36-b53a-4749-87e6-8815da99bac7",
    "name": "Intersection-Demo",
    "latitude": 33.3091336,
    "longitude": -111.9353095
  },
  "mqtt": {
    "host": "broker.scenescape.intel.com",
    "port": 1883,
    "use_tls": true,
    "ca_cert_path": "secrets/certs/scenescape-ca.pem",
    "camera_topics": [
      "scenescape/data/camera/camera1",
      "scenescape/data/camera/camera2",
      "scenescape/data/camera/camera3",
      "scenescape/data/camera/camera4"
    ]
  },
  "vlm": {
    "base_url": "http://vlm-openvino-serving:8000",
    "model": "Qwen/Qwen2.5-VL-3B-Instruct",
    "timeout_seconds": 300
  },
  "traffic": {
    "high_density_threshold": 10,
    "analysis_window_seconds": 30,
    "vlm_trigger_duration_seconds": 15
  }
}
```

Note: Configuration values can be overridden by environment variables set in `setup.sh`.

## Next Steps

- **Overview**: For detailed architecture, key components, see [Overview](./Overview.md)  
- **API Documentation**: Explore the Traffic Intelligence API at `http://localhost:8081/docs` (Swagger UI)
- **Advanced Configuration**: For detailed environment variable options, see [Environment Variables](./environment-variables.md)
- **SceneScape Management**: Access the web interface at `https://localhost:443` for visual management
- **Build from Source**: See [How to Build from Source](./how-to-build-from-source.md) for development and custom builds
- **Troubleshooting**: If you encounter issues, check the [Troubleshooting Guide](./troubleshooting.md)


