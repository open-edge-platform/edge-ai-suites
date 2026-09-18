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

## Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_ROUTE_PLANNER_PORT` | `7864` | Port on which the Smart Route Planning Agent UI is accessible. |

## Reasoning Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OVMS_CACHE_SIZE` | `10` | Value for KV cache in GiB. Increase this value for better performance. |
| `REASONING_TIMEOUT_SEC` | `15.0` | Timeout in seconds for the reasoning model. Increase this value for larger models or slower hardware. |

#### Example:

```bash
export OVMS_CACHE_SIZE=20
export REASONING_TIMEOUT_SEC=30.0
```


## Proxy Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `http_proxy` | (system) | HTTP proxy URL for outbound connections. |
| `https_proxy` | (system) | HTTPS proxy URL for outbound connections. |
| `no_proxy` | (system) | Comma-separated list of hosts to bypass proxy. `HOST_IP` is automatically added. |

## Set Environment Variables

The setup script automatically configures most environment variables. To override defaults, export variables before running the script.

Here are some example values being set and then used to run the application :

```bash
export AI_ROUTE_PLANNER_PORT=8080
export LOG_LEVEL=DEBUG
export TAG=latest
export LOG_LEVEL=INFO
export TRAFFIC_BUFFER_DURATION=60
export DATA_RETENTION_HOURS=24
source setup.sh --run
```
