# Build from Source

> **NOTE :** This is for advanced user only and we recommend pulling the already built image and running the application using it. See [this](../get-started.md) to run the application without building.

This section shows how to build the Smart Route Planning Agent from source and run it along with all its dependencies.

## Prerequisites

1. Set the reasoning AI model to be used:

    ```bash
    export REASONING_MODEL_NAME=<model-name>    # e.g. OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov
    ```

2. _**(Optional)**_ Set tag for the image to be built:

    ```bash
    export TAG=<build_tag>      # e.g.  dev-081726
    ```

    This tag will be used for building the image locally and running the application. If not set, default tag `latest` would be used.


3. Configure the Smart Traffic Intersection Agent Endpoints:

    Edit `src/data/config.json` to add the IP addresses and ports of the nodes where _Smart Traffic Intersection Agents_ are running:

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

You can also configure only a single instance, but a minimum of three _Smart Traffic Intersection Agent_ instances is recommended for proper route planning.

## Build from Source and Run the Application

1. Clone the application source code:

```bash
   git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/smart-route-planning-agent
```

2. Build the image from source and run the application suite:

```bash
source setup.sh --setup
```

This builds the `intel/smart-route-planning-agent:<build_tag>` image locally and runs the entire application suite.
If `TAG` variable is not set, image will be built as `intel/smart-route-planning-agent:latest`.

The UI URL is displayed when the application is successfully run: `http://<host-ip>:7864`. Open it in your browser to access the application.


### Alternative Setup

You can also first build the image and the run the application in following two separate steps:

1. Build the docker image:

```bash
source setup.sh --build
```

2. Once the image is built successfully, run the _Smart Route Planning Agent_ along with its dependencies:

```bash
source setup.sh --run
```


### Stop the Application

To stop the application:

```bash
source setup.sh --stop
```

This will stop and remove all the containers for the application and its dependencies.
