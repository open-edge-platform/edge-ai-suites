# Get Started

This application uses AI Agent to analyze a route between given source and destination. It communicates with other agents to fetch live analysis reports for traffic intersections found along all feasible routes between the source and destination. Subsequently, the agent finds an optimum route in real-time which is likely to be free from any possible incidents (like congestion, weather, roadblocks, accidents etc.).

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

The Smart Route Planning Agent includes a unified setup script (`setup.sh`) that combines both setup and orchestration functionality. It handles environment configuration, building, deployment, and ongoing service management. This is the **recommended approach** for getting started and managing the services.

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/smart-route-planning-agent
```

### 2. Run the Complete Setup

The setup script provides several options. For a complete setup (recommended for first-time users):

```bash
source setup.sh --setup
```

### 3. Alternative Setup Options

For more granular control, the setup script provides individual commands:

```bash
# Start services only (after setup)
source setup.sh --run

# Stop services
source setup.sh --stop

# Restart services
source setup.sh --restart
```


## Manual Setup (Advanced Users)

For advanced users who need more control over the configuration, you can manually set up the stack using Docker Compose.

### Manual Environment Configuration

If you prefer to manually configure environment variables instead of using the setup script, see the [Environment Variables Guide](./environment-variables.md) for complete details.

### Manual Docker Compose Deployment

See [Build from Source](./build-from-source.md) for instructions on building and running with Docker Compose.

## Multi-Node Deployment

The Smart Route Planning Agent is designed to work in a multi-node setup with one central Route Planning Agent and multiple Smart Traffic Intersection Agent edge nodes.

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

1. Deploy [Smart Traffic Intersection Agent](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-traffic-intersection-agent/docs/user-guide/get-started.md#quick-start-with-setup-script) on each edge node.
2. Ensure network connectivity between the central node and all edge nodes.
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
