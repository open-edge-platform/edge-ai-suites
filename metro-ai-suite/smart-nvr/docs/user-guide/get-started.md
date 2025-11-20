# Smart NVR - Getting Started

## Overview

Smart NVR is a GenAI-powered video analytics application that transforms traditional network video recorders with intelligent event detection and real-time insights at the edge. This guide will walk you through deploying and configuring the application to extract valuable insights from your video data.

## Prerequisites

### System Requirements
- System must meet [minimum requirements](./system-requirements.md)
- 3-4 devices for distributed deployment

Smart NVR operates in a distributed architecture requiring multiple services across 3-4 devices for optimal performance:

| Device | Service | Purpose |
|--------|---------|---------|
| Device 1 | VSS Search | Video search functionality |
| Device 2 | VSS Summary | Video summarization |
| Device 3 | VLM Microservice | AI-powered event descriptions (optional) |
| Device 3/4 | Smart NVR App | Main application interface |

### Software Dependencies
- **Docker**: [Installation Guide](https://docs.docker.com/get-docker/)
  - Must be configured to run without sudo ([Post-install guide](https://docs.docker.com/engine/install/linux-postinstall/))
- **Git**: [Installation Guide](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

### Required Services

Before setting up Smart NVR, ensure these services are running on their respective devices:

#### 1. VSS (Video Search and Summarization) Services
Deploy these on separate devices:
- **VSS Search**: Handles video search functionality
- **VSS Summary**: Provides video summarization capabilities

📖 [VSS Documentation](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/video-search-and-summarization/docs/user-guide/get-started.md)

#### 2. VLM Microservice (Optional)
Required only when enabling AI-powered event descriptions (`NVR_GENAI=true`):
- Runs the VLM model defined in the frigate [config file](../../resources/frigate-config/config.yml)
- Use `VLM_MAX_COMPLETION_TOKENS` to limit response length during deployment

📖 [VLM Serving Documentation](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/vlm-openvino-serving/docs/user-guide/get-started.md)

## Quick Start

### Step 1: Clone the repo

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/smart-nvr
```

### Step 2: Configure Environment

Set up the required environment variables:

```bash
# Docker Registry Details
export REGISTRY_URL="intel"
export TAG="1.2.1"

# VSS Service Endpoints
export VSS_SUMMARY_IP=<vss-summary-device-ip>
export VSS_SUMMARY_PORT=<vss-summary-port>        # Default: 12345
export VSS_SEARCH_IP=<vss-search-device-ip>
export VSS_SEARCH_PORT=<vss-search-port>          # Default: 12345

# MQTT Configuration
export MQTT_USER=<mqtt-username>
export MQTT_PASSWORD=<mqtt-password>

# Feature Toggles
export NVR_GENAI=false                  # Set to 'true' to enable AI-powered event descriptions
export NVR_SCENESCAPE=false             # Set to 'true' to enable Scenescape integration
```

### Step 3: Launch Application

```bash
# Start all services
source setup.sh start
```

This launches all required containers:

![Services overview](./_images/containers.png)

### Step 4: Access the Interface

Open your browser and navigate to:
```
http://<host-ip>:7860
```

### Step 5: Stop Services

```bash
# Stop all services when done
source setup.sh stop
```

## Advanced Configuration

### Enabling AI-Powered Event Descriptions

To enable Smart NVR's GenAI capabilities for intelligent event descriptions:

#### 1. Update Frigate Configuration
Modify `resources/frigate-config/config.yml`:

```yaml
genai:
  enabled: true
```

#### 2. Ensure VLM Service Availability
Verify the VLM microservice is running and accessible at the configured endpoint.

#### 3. Set Environment Variable
```bash
export NVR_GENAI=true
export VLM_SERVING_IP=<vlm-serving-device-ip>
export VLM_SERVING_PORT=<vlm-serving-port>
```

#### 4. Run the application

Re-run the application after [configuring](./get-started.md#step-2-configure-environment) the rest of environment variables. Ensure that the environment value `export NVR_GENAI=true` is set.

> **⚠️ Important Notes**:
> - This feature is experimental and may be unstable due to underlying Frigate GenAI implementation
> - Requires VLM microservice to be running
> - Disabled by default for system stability

## Running Tests and Generating Coverage Report

To ensure the functionality of the microservice and measure test coverage, follow these steps:

1. **Install Dependencies**
   Install the required dependencies, including development dependencies, using:

   ```bash
   poetry install --with test
   ```

2. **Run Tests with Poetry**
   Use the following command to run all tests:

   ```bash
   poetry run pytest
   ```

3. **Run Tests with Coverage**
   To collect coverage data while running tests, use:

   ```bash
   poetry run pytest --cov=src --cov=ui --cov-report=term-missing:skip-covered
   ```

4. **Generate Coverage Report**
   After running the tests, generate a coverage report:

   ```bash
   poetry run coverage report -m
   ```

5. **Generate HTML Coverage Report (Optional)**
   For a detailed view, generate an HTML report:

   ```bash
   poetry run coverage html
   ```

   Open the `htmlcov/index.html` file in your browser to view the report.

These steps will help you verify the functionality of the microservice and ensure adequate test coverage.

### Scenescape Integration

For traffic analytics capabilities with Intel Scenescape (vehicle counting, traffic flow analysis), see the **[Scenescape Integration Guide](./scenescape-integration.md)**.

### Custom Build Configuration

If using custom [build flags](./how-to-build-from-source.md#customizing-the-build), ensure the same environment variables are set before running the setup script.

## Next Steps

1. **Explore Features**: Learn about application capabilities in the [How to Use Guide](./how-to-use-application.md)
2. **Troubleshooting**: If you encounter issues, check the [Troubleshooting Guide](./Troubleshooting.md)
