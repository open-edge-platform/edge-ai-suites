# Build from Source

This section shows how to build the Smart Traffic Intersection Agent from source to customize or extend its functionality.

## Prerequisites

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Docker platform**: Install Docker platform from [Get Docker](https://docs.docker.com/get-docker/).
- Basic familiarity with Git and Docker commands.

## Build Traffic Intersection Agent

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd metro-ai-suite/smart-traffic-intersection-agent/
```

### 2. Build the Docker Image

Build the Traffic Intersection Agent:

```bash
docker compose -f docker/agent-compose.yaml build traffic-intersection-agent
```

### 3. Run the Service

```bash
# Using setup script (recommended)
source setup.sh --run

# Or manually with Docker Compose
docker compose -f docker/agent-compose.yaml up traffic-intersection-agent
```

### 4. Verify the Build

```bash
# Check service health
curl http://localhost:8081/health

# Access UI
curl http://localhost:7860/

# View logs
docker compose -f docker/agent-compose.yaml logs traffic-intersection-agent
```

### Verify API Endpoints

```bash
# Health check
curl http://localhost:8081/health

# Get current traffic data
curl http://localhost:8081/api/v1/traffic/current
```

## Rebuild After Changes

After you have edited the code, rebuild:

```bash
# Rebuild the image
docker compose -f docker/agent-compose.yaml build traffic-intersection-agent

# Restart the service
docker compose -f docker/agent-compose.yaml up -d traffic-intersection-agent

# View startup logs
docker compose -f docker/agent-compose.yaml logs traffic-intersection-agent
```

## Learn More

- [Get Started Guide](../get-started.md)
<!--- TODO [Environment Variables](./environment-variables.md)-->
- [System Requirements](./system-requirements.md)
