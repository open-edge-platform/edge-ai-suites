# Get Started

Smart NVR is a GenAI-powered video analytics application that transforms traditional network
video recorders with intelligent event detection and real-time insights at the edge. This guide
will walk you through deploying and configuring the application to extract valuable insights
from your video data.

## Prerequisites

### System Requirements

- System must meet [minimum requirements](./get-started/system-requirements.md).
- VSS and Smart NVR can run on the same device using VSS Dual Mode, or on separate devices.

| Deployment Option | VSS Mode | Minimum Devices |
| ----------------- | -------- | --------------- |
| Single device | Dual Mode (`--summary --search`) | 1 |
| Separate VSS device | Any mode | 2 |
| With GenAI (optional) | Any | +1 for VLM Microservice |

Deploy VSS before starting Smart NVR. See [VSS Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/video-search-and-summarization/get-started.html) for setup instructions.

### Software Dependencies

- **Docker**: [Installation Guide](https://docs.docker.com/get-docker/)
  - Must be configured to run without sudo ([Post-install guide](https://docs.docker.com/engine/install/linux-postinstall/))
- **Git**: [Installation Guide](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

## Quick Start

### Step 1: Build from Source

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/smart-nvr
```

### Step 2: Configure Environment

Set up the required environment variables:

```bash
# Docker Registry Details
export REGISTRY_URL="intel"
export TAG="latest"

# VSS Service Endpoint (required)
export VSS_IP=<vss-device-ip>
export VSS_PORT=<vss-port>                         # optional, default 12345

# Optional — set only if needed
# export NVR_SCENESCAPE=false           # optional, default false; set to 'true' to enable Scenescape integration
# export http_proxy=<http-proxy>
# export https_proxy=<https-proxy>
# export no_proxy=<no_proxy>
# export MQTT_USER=<mqtt-username>      # auto-generated if omitted
# export MQTT_PASSWORD=<mqtt-password>  # auto-generated if omitted
```

### Step 3: Launch Application

```bash
# Start all services
source setup.sh start
```

The batch settings control how the NVR Event Router groups videos detected by
the continuous-ingestion watcher, and how often it polls Pipeline Manager for
asynchronous embedding-job completion. They do not affect single event-rule
clips or video summarization.

This launches all required containers:

![Services overview](./_assets/containers.png "services overview")

### Step 4: Access the Interface

Open your browser and navigate to:

```text
http://<host-ip>:7860
```

### Step 5: Stop Services

```bash
# Stop all services when done
source setup.sh stop
```

## Advanced Configuration

For optional features including AI-powered event descriptions (GenAI) and custom build options, see the **[Advanced Configuration Guide](./advanced-configuration.md)**.

### Scenescape Integration

For traffic analytics capabilities with Scenescape (vehicle counting, traffic flow analysis), see the **[Scenescape Integration Guide](./scenescape-integration.md)**.

### Custom Build Configuration

If using custom [build flags](./get-started/build-from-source.md#customizing-the-build),
ensure the same environment variables are set before running the setup script.

## Next Steps

1. **Explore Features**: Learn about application capabilities in the [How to Use Guide](./how-to-use-application.md)
2. **Troubleshooting**: If you encounter issues, check the [Troubleshooting Guide](./troubleshooting.md)

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements
./get-started/build-from-source
./get-started/deploy-with-helm
./advanced-configuration

:::
hide_directive-->
