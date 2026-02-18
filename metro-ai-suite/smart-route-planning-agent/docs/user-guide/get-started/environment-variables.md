# Environment Variables

This section explains the environment variables used to configure the Smart Route Planning Agent.

1. [Core Configuration](#core-configuration)
2. [Network Configuration](#network-configuration)
3. [Application Settings](#application-settings)
4. [Proxy Settings](#proxy-settings)

## Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_IP` | Auto-detected | Host IP address for the application. Automatically detected from the network interface. Falls back to `127.0.0.1` if detection fails. |
| `TAG` | `latest` | Docker image tag to use when building and running containers. |
| `REGISTRY` | (empty) | Docker registry path for pulling or pushing images. |

## Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_ROUTE_PLANNER_PORT` | `7864` | Port on which the Smart Route Planning Agent UI is accessible. |

## Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAFFIC_BUFFER_DURATION` | `60` | Duration in seconds for traffic data buffering. |
| `LOG_LEVEL` | `INFO` | Logging level for the application. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DATA_RETENTION_HOURS` | `24` | Number of hours to retain traffic data. |

## Proxy Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `http_proxy` | (system) | HTTP proxy URL for outbound connections. |
| `https_proxy` | (system) | HTTPS proxy URL for outbound connections. |
| `no_proxy` | (system) | Comma-separated list of hosts to bypass proxy. `HOST_IP` is automatically added. |

## Set Environment Variables

### Configure Using the Setup Script (Recommended)

The setup script automatically configures most environment variables. To override defaults, export variables before running the script:

```bash
export AI_ROUTE_PLANNER_PORT=8080
export LOG_LEVEL=DEBUG
source setup.sh --setup
```

### Configure Manually

For manual deployment, create a `.env` file in the `src/` directory:

```bash
HOST_IP=192.168.1.100
AI_ROUTE_PLANNER_PORT=7864
TAG=latest
LOG_LEVEL=INFO
TRAFFIC_BUFFER_DURATION=60
DATA_RETENTION_HOURS=24
```

Run the Docker Compose tool:

```bash
cd src
docker compose --env-file .env up
```
