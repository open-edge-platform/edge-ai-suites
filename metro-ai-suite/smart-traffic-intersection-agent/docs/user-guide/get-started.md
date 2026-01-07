# Get Started

The **Scene Intelligence microservice** provides comprehensive traffic analysis capabilities including real-time intersection monitoring, directional traffic density analysis, and VLM-powered traffic insights. This guide provides step-by-step instructions to:

- Set up the microservice using the automated setup script for quick deployment.
- Run predefined tasks to explore its functionality.
- Learn how to modify configurations to suit specific requirements.

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).
- **MQTT Broker**: Ensure access to an MQTT broker for traffic data streaming (or use the included broker).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

The Scene Intelligence microservice includes an automated setup script that handles environment configuration, secrets generation, building, and deployment. This is the **recommended approach** for getting started.

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git
cd edge-ai-libraries/microservices/scene-intelligence
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

The setup command starts all services including the containerized Traffic Intelligence service.

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

## Services Included

The Scene Intelligence stack includes these containerized services:

- **MQTT Broker** (Eclipse Mosquitto) - Message broker for traffic data
- **DL Streamer Pipeline Server** - Video analytics and AI inference
- **SceneScape Database** - Configuration and metadata storage
- **SceneScape Web Server** - Management interface
- **SceneScape Controller** - Orchestration service
- **VLM OpenVINO Serving** - Vision Language Model inference
- **Traffic Intelligence** - Real-time traffic analysis with dual interface (API + UI)

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

## Service Ports

The complete stack exposes several services on different ports:

| Service | Port | Description |
|---------|------|-------------|
| Scene Intelligence API | 8082 | Main traffic analysis API |
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

- **Traffic Intelligence**: Access the UI dashboard at `http://localhost:7860` for interactive traffic monitoring
- **API Documentation**: Explore the Traffic Intelligence API at `http://localhost:8081/docs` (Swagger UI)
- **Advanced Configuration**: For detailed environment variable options, see [Environment Variables](./environment-variables.md)
- **Traffic Analysis Deep Dive**: See [Traffic Data Analysis Workflow](./traffic-data-analysis-workflow.md) for VLM integration details
- **SceneScape Management**: Access the web interface at `https://localhost:443` for visual management
- **Video Analytics**: Configure video streams through DL Streamer integration
- **Build from Source**: See [How to Build from Source](./how-to-build-from-source.md) for development and custom builds


### Key Integration Points

- **MQTT Communication**: All services communicate via the shared MQTT broker
- **Docker Network**: Services discover each other via Docker service names
- **Shared Secrets**: TLS certificates and auth files mounted from `src/secrets/`
- **Persistent Storage**: Traffic data stored in Docker volume `traffic-intelligence-data`
- **Health Monitoring**: All services include health check endpoints

## Troubleshooting

### Stack Not Starting

Check status and logs:

```bash
# View container status
docker ps -a

# Check specific service logs
docker compose -f docker/compose.yaml logs traffic-intelligence
docker compose -f docker/compose.yaml logs vlm-openvino-serving
docker compose -f docker/compose.yaml logs broker

# Restart services
source setup.sh --stop
source setup.sh --run
```

Common issues:
- Missing secrets/certificates in `src/secrets/` directory
- Port conflicts (check ports 8081, 7860, 9764, 443, 1883, 8555)
- Insufficient system resources for VLM service
- Proxy configuration issues

### Traffic Intelligence Service Issues

Check service health:

```bash
# Verify API is responding
curl http://localhost:8081/health

# Check UI accessibility
curl http://localhost:7860/

# View detailed logs
docker logs -f scene-intelligence-traffic-intelligence

# Check container is running
docker ps | grep traffic-intelligence
```

### Service Health Issues

Verify individual service health:

```bash
# Traffic Intelligence
curl http://localhost:8081/health

# VLM Service
curl http://localhost:9764/health

```

### MQTT Connection Issues

Verify MQTT broker connectivity:

```bash
# Check broker is running
docker ps | grep broker

# Verify certificate is mounted
docker exec scene-intelligence-traffic-intelligence ls -la /app/secrets/certs/

# Check network connectivity
docker compose -f docker/compose.yaml exec traffic-intelligence ping broker.scenescape.intel.com
```

### VLM Analysis Not Working

Debug VLM integration:

```bash
# Check VLM service health
curl http://localhost:9764/health

# Verify traffic threshold configuration
curl http://localhost:8081/api/v1/config

# Check camera data availability
docker logs scene-intelligence-traffic-intelligence | grep "camera"

# Monitor VLM requests
docker logs scene-intelligence-traffic-intelligence | grep -i vlm
```

### Performance Issues

Monitor resource usage:

```bash
# Check container resource usage
docker stats

# Adjust VLM workers if needed
export VLM_WORKERS=2
docker compose -f docker/compose.yaml up -d vlm-openvino-serving
```

### Configuration Issues

Validate configuration files:

```bash
# Check JSON syntax
cat src/traffic-intelligence/config/traffic_intelligence.json | jq .
cat config/scene_intelligence_config.json | jq .

# Verify mounted configuration
docker compose -f docker/compose.yaml exec traffic-intelligence ls -la /app/config/
```
