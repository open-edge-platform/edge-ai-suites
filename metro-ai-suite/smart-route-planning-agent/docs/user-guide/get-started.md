# Get Started

## Prerequisites

- **System requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).

- **Docker platform**: Install Docker platform. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).

- You are familiar with Docker commands and using the terminal. If you are new to Docker platform, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

Intel recommends using the unified setup script `setup.sh` that configures, builds, deploys, and manages the Smart Route Planning Agent. 

1. Clone the repository:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/smart-route-planning-agent
```

2. Run the complete setup:

The setup script provides several options. For a complete setup (recommended for first-time users):

```bash
source setup.sh --setup
```

3. Run alternative setup options

For a more granular control, run these commands:

```bash
# Start services only (after setup)
source setup.sh --run

# Stop services
source setup.sh --stop

# Restart services
source setup.sh --restart
```


## Manual Setup for Advanced Users

For advanced users who need more control over the configuration, you can set up the stack manually using Docker Compose tool.

### Manual Environment Configuration

If you prefer to configure environment variables manually instead of using the setup script, see the [Environment Variables Guide](./environment-variables.md) for details. 

### Manual Docker Compose Tool Deployment

See [Build from Source](./build-from-source.md) for instructions on building and running with the Docker Compose tool.

## Multi-Node Deployment

The Smart Route Planning Agent works in a multi-node setup with one central Route Planning Agent and multiple Smart Traffic Intersection Agent edge nodes.

### Architecture Overview

```
                    ┌─────────────────────────────┐
                    │  Smart Route Planning Agent │
                    │       (Central Node)        │
                    └──────────────┬──────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ Smart Traffic       │ │ Smart Traffic       │ │ Smart Traffic       │
│ Intersection Agent  │ │ Intersection Agent  │ │ Intersection Agent  │
│ (Edge Node 1)       │ │ (Edge Node 2)       │ │ (Edge Node N)       │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

### Prerequisites

1. Deploy the [Smart Traffic Intersection Agent](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-traffic-intersection-agent/docs/user-guide/get-started.md#quick-start-with-setup-script) on each edge node.
2. Ensure network connectivity between the central node and edge nodes.
3. Note the IP address and port of each Smart Traffic Intersection Agent.

### Configure Edge Node Endpoints

Edit `src/data/config.json` to add the IP addresses of your Smart Traffic Intersection Agent edge nodes:

```json
{
    "api_endpoint": "/api/v1/traffic/current?images=false",
    "api_hosts": [
        {
            "name": "Intersection-1",
            "host": "http://<edge-node-1-ip>:8081"
        },
        {

            "name": "Intersection-2",
            "host": "http://<edge-node-2-ip>:8082"
        },
        {

            "name": "Intersection-3",
            "host": "http://<edge-node-3-ip>:8083"
        }
    ]
}
```

Replace `<edge-node-X-ip>` with the actual IP addresses of your edge nodes.

### Deploy the Route Planning Agent

After configuring the edge node endpoints, deploy the Smart Route Planning Agent on the central node:

```bash
source setup.sh --setup
```

The Route Planning Agent will query all configured Smart Traffic Intersection Agents to gather live traffic data for route optimization.
