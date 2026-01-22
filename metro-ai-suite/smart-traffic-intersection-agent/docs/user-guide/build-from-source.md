# How to Build from Source

Build the Scene Intelligence microservice from source to customize or extend its functionality. This guide covers building the containerized Traffic Intersection Agent.

## Prerequisites

- **System Requirements**: Verify your system meets the [minimum requirements](./system-requirements.md).
- **Docker**: Install Docker from [Get Docker](https://docs.docker.com/get-docker/).
- Basic familiarity with Git and Docker commands.

## Build Traffic Intersection Agent

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git
cd edge-ai-libraries/microservices/scene-intelligence
```

### 2. Build the Docker Image

Build the Traffic Intersection Agent:

```bash
docker compose -f docker/compose.yaml build traffic-intersection-agent
```

### 3. Run the Service

```bash
# Using setup script (recommended)
source setup.sh --run

# Or manually with Docker Compose
docker compose -f docker/compose.yaml up traffic-intersection-agent
```

### 4. Verify the Build

```bash
# Check service health
curl http://localhost:8081/health

# Access UI
curl http://localhost:7860/

# View logs
docker compose -f docker/compose.yaml logs traffic-intersection-agent
```

### Verify API Endpoints

```bash
# Health check
curl http://localhost:8081/health

# Get current traffic data
curl http://localhost:8081/api/v1/traffic/current
```

## Rebuild After Changes

When you modify code:

```bash
# Rebuild the image
docker compose -f docker/compose.yaml build traffic-intersection-agent

# Restart the service
docker compose -f docker/compose.yaml up -d traffic-intersection-agent

# View startup logs
docker compose -f docker/compose.yaml logs traffic-intersection-agent
```


## Supporting Resources

- [Get Started Guide](get-started.md)
- [Environment Variables](environment-variables.md)
- [System Requirements](system-requirements.md)

