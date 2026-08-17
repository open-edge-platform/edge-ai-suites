# Get Started

## Prerequisites

- **System requirements**: Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).

- **Docker platform**: Install Docker platform. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).

- You are familiar with Docker commands and using the terminal. If you are new to Docker
platform, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

1. **Clone the Repository :**

   If you want to clone a specific release branch, replace `main` with the desired tag.
   To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

   ```bash
   git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/smart-route-planning-agent
   ```

2. **Configure _Smart Traffic Intersection Agent_ Node Endpoints :**

    In order to plan routes, **Smart Route Planning Agent** needs **_Smart Traffic Intersection Agents_** running on pre-defined nodes. See [this](#multi-node-stack-for-smart-route-planning-agent) to learn more.

    Edit `src/data/config.json` to add the IP addresses and ports of the edge nodes where Smart Traffic Intersection Agents are running.

    #### Example Configuration

    ```json
    {
        "api_endpoint": "/api/v1/traffic/current/ws?images=false",
        "api_hosts": [
            {
                "host": "ws://<node-1-ip>:<port>"
            },
            {
                "host": "ws://<node-2-ip>:<port>"
            },
            {
                "host": "ws://<node-3-ip>:<port>"
            }
        ]
    }
    ```

3. **Set the required environment variables :**

    ```bash
    export REASONING_MODEL_NAME=<model-name>    # e.g. OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov
    export TAG=latest   # Make sure TAG is set to latest to pull the latest image.
    ```

4. **Run the _Smart Route Planning Agent_ along with all dependencies :**

   ```bash
   source setup.sh --run
   ```

> **Note**: When deployed for the first time, the AI model is downloaded and converted to required format. This can take several minutes depending on your network. This model is later cached in a Docker volume, so that restarts or next deployments with same models are fast. Set `HF_TOKEN` environment variable, as well, if the model repository is gated.

### Stop the application :

   To stop and remove the containers for the application and its dependencies :

   ```bash
   source setup.sh --stop
   ```

   To restart the application along with all the dependencies :

   ```bash
   source setup.sh --restart
   ```

   To stop application along with cleaning up all the associated volumes and images:
   _(**Caution:** This will remove all downloaded AI models for the application. Next run will re-download these models.)_

   ```bash
   source setup.sh --clean
   ```


### Validated AI Models

The following models were measured on a general purpose x86 CPU:

| Model | Precision | Suitability |
| --- | --- | --- |
| `OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov` | INT4 | Comfortably within budget, and it supports schema constrained output. |
| `OpenVINO/Qwen2.5-1.5B-Instruct-int8-ov` | INT8 | It supports schema constrained output. Requires comparatively more storage and inference time. |


On slower hardware prefer a smaller INT4 model.

> **Note**: Before adopting a model that is not listed above, please validate it for the map updates in the UI without the fallback notice. If the OVMS container restarts repeatedly, the model is most likely not compatible.

### Fallback behaviour

The agent automatically falls back to rule based planning for that update, whenever:

- the model server is unreachable, still loading, or times out,
- the model could not make a decision
- the model hullucinates (For example, names a route that does not exist or has no live traffic data.)

## Manual Setup for Advanced Users

For advanced users who need more control over the configuration, you can set up the stack
manually using Docker Compose tool.

### Manual Environment Configuration

If you prefer to configure environment variables manually instead of using the setup script,
see the [Environment Variables Guide](./get-started/environment-variables.md) for details.

### Build from Source and Deploy

See [Build from Source](./get-started/build-from-source.md) for instructions on building and
running with the Docker Compose tool.

### Helm Deployment

See [Deploy with Helm](./get-started/deploy-with-helm.md) for a simple Kubernetes deployment flow.

## Multi-Node Stack for Smart Route Planning Agent

The Smart Route Planning Agent works in a multi-node setup with one central _Smart Route Planning Agent_ and multiple _Smart Traffic Intersection Agent_ edge nodes.

### Architecture Overview

![Architecture Overview](./_assets/smart-route-agent-architecture-overview.svg "Architecture Overview")

### Multi-Node Deployment Prerequisites

1. Deploy the [Smart Traffic Intersection Agent](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/smart-traffic-intersection-agent/get-started.html#quick-start-with-setup-script) on each edge node.
2. Ensure network connectivity between the central node and edge nodes.
3. Note the IP address and port of each Smart Traffic Intersection Agent.
4. Update the `api_hosts` field in the `src/data/config.json` file with all the edge node's IP address and port. See [this](#quick-start-with-setup-script) for example configuration.

> **NOTE :** We can add `api_hosts` for even just one instance, however minimum three instances of Smart Traffic Intersection Agent is recommended for proper route planning in the application.

### Deploy the Route Planning Agent

After configuring the edge node endpoints, deploy the Smart Route Planning Agent on the
central node:

```bash
source setup.sh --run
```

The Route Planning Agent will query all configured Smart Traffic Intersection Agents to gather
live traffic data for route optimization.

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements
get-started/build-from-source
get-started/environment-variables
get-started/deploy-with-helm

:::
hide_directive-->
