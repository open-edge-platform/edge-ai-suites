# Get Started

The **Smart Traffic Intersection Agent (STIA)** provides comprehensive traffic analysis capabilities including real-time intersection monitoring, directional traffic density analysis, and VLM-powered traffic insights. This guide provides step-by-step instructions to:

- Set up the agent using the automated setup script for quick deployment.
- Run predefined tasks to explore its functionality.
- Learn how to modify configurations to suit specific requirements.

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).
- **MQTT Broker**: Ensure access to an MQTT broker for traffic data streaming (or use the included broker).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

The Smart Traffic Intersection Agent includes an automated setup script that handles environment configuration, submodule and dependencies setup, secrets generation, building, and deployment. This is the **recommended approach** for getting started.

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd metro-ai-suite/smart-traffic-intersection-agent/
```

### 2. Run the Complete Setup

Easiest way to setup the service is to use the default configurations without making any changes. Run the setup script with --setup option for quick setup of the application with default configuration :

```bash
source setup.sh --setup
```

This single command will:

- Set all required environment variables with default values
- Setup all dependencies and submodules required for Traffic Intersection Agent
- Generate required TLS certificates and authentication files
- Download demo video files for testing
- Build Docker images
- Start all services in the Traffic Intersection Agent application stack

### 3. Access Services

Once the script is completed successfully, it will show the URLs to access the services. Head to these URLs for the respective services to access them in a web browser.

## Running Multiple Instances (Test/Dev Only)

For testing or development purposes, you might want to run multiple instances of the Smart Traffic Intersection Agent to simulate multiple intersections on the same development machine/node. Easiest way to do this is to clone and setup the application `n times` in n different locations on the same machine for `n` required instances. Please note that in production environments, only a single Traffic Intersection Agent instance is deployed on a given node.

> **Recommendation**: The number of instances you can run on a single machine, depends on available resources. Systems with higher resources can support more instances.

### Setting up Instance #1

#### 1. Clone the repository into a new directory:

```bash
# First instance
git clone --depth 1 https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites-instance1
cd edge-ai-suites-instance1/metro-ai-suite/smart-traffic-intersection-agent/
```

#### 2. Edit deployment config file for Instance #1

```bash
nano src/config/deployment_instance.json
```

Update the `latitude` and `longitude` values as required. If not required, use the default values without updating this config file. Following is a sample value for the Instance #1 deployment config:

```json
{
    "name": "intersection_1",
    "latitude": 37.7049108,
    "longitude": -121.9096158,
    "agent_backend_port": "8081",
    "agent_ui_port": "7860"
}
```

#### 3. Run Setup for Instance #1

```bash
source setup.sh --setup
```

### Setting up Instance #2

#### 1. Clone the repository into a new directory:

Open a new terminal window and move to different directory and run the following.

```bash
git clone --depth 1 https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites-instance2
cd edge-ai-suites-instance2/metro-ai-suite/smart-traffic-intersection-agent/
```

#### 2. Edit deployment config for Instance #2

```bash
nano src/config/deployment_instance.json
```

Following is a sample value for the Instance #2 deployment config:

```json
{
    "name": "intersection_2",
    "latitude": 37.33874,
    "longitude": -121.8852525,
    "agent_backend_port": "8082",
    "agent_ui_port": "7861"
}
```
#### 3. Run Setup for Instance #2

```bash
source setup.sh --setup
```

> __**NOTE**__ : Keep `agent_backend_port` and `agent_ui_port` values empty to use random ephemeral ports and avoid port conflicts.


Ensure each instance has their `deployment_instance.json` updated with:
- A unique value for `name` field
- Unique latitude and longitude co-ordinates
- Different `agent_backend_port` and `agent_ui_port` values to avoid port conflicts (optional — if not specified, an ephemeral port is picked automatically)

### Deploying more instances

There are functionally no limits on number of instances which you can spin-up to simulate multi-node setup using the provided script. However, the machine on which the multiple deployment is being done, will likely start throttling these instances if resource limits are reached. Hence, deploy new instances only if you have the required resource bandwidth.

To spin-up more instances - say `n number of new instances`, repeat the steps mentioned to [Setting up Instance #2](#setting-up-instance-2), by changing to a new directory `n` times.


## Advanced Environment Configuration

For advanced users who need more control over the configuration, following environment variables can be configured before running the setup script to override the default behaviour.
 
```bash
# Set log level to debug to help in debugging issues, default value is info
export LOG_LEVEL=DEBUG

# Change the VLM Model name. Default value set in script.sh is microsoft/Phi-3.5-vision-instruct.
export VLM_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct

# Other VLM related config, sample values
export VLM_TIMEOUT_SECONDS=600          # Default 300
export VLM_MAX_COMPLETION_TOKENS=1000   # Default 1500
export VLM_TEMPERATURE=0.4              # Default 0.1, range 0-1; controls randomness of response
export VLM_TOP_P=0.3                    # Default 0.1, range 0-1; another parameter to control randomness and diversity of response

# Some sample values for Traffic Intersection configuration
export HIGH_DENSITY_THRESHOLD=5        # Default value 10
export MODERATE_DENSITY_THRESHOLD=3    # Default value 5; Make sure this is less than HIGH_DENSITY_THRESHOLD
export TRAFFIC_BUFFER_DURATION=20      # Default value 30; Analysis window of traffic feeds in seconds 
```


## Accessing the Services

As the setup process, as mentioned above, completes successfully, the URLs for all services are displayed on the terminal. We can get the URL for **Traffic Intersection Agent UI** and **Traffic Intersection Agent API Docs** from the response and access it in a web browser.

Following is a sample response you might get at the completion of script, which displays all the URLs to access the relevant services:

![alt text](./_images/service_endpoints.png)


## Troubleshooting

### Port Conflicts for Traffic Intersection Agent Backend or UI

Please make sure the the config file at `src/config/deployment_instance.json` for all instances (deployed from different directories, in case of multiple deployment on same machine) has empty values for following fields `agent_backend_port`, `agent_ui_port` as follows: 

```bash
    ...
    "agent_backend_port": "",
    "agent_ui_port": ""
    ...
```

It is recommended to keep these values empty and let Docker use ephemeral ports for minimal hassle. However, if it is required to provide a explicit port, then make sure all such port values for all instances are unique. Also, make sure no other external services are running on these ports.

