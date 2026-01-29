# Build from source

This guide provides step-by-step instructions for building the `Time Series Analytics`
microservice and `industrial-edge-insights-multimodal` Sample Application from source.
Follow the [prerequisites](../get-started.md#configure-docker) and ensure you understand the
[data flow explanation](../weld-defect-detection/index.md#data-flow-explanation)
before proceeding with the following steps.

## Steps to Build from Source

1. **Clone the source and build the `Time Series Analytics` microservice**.

    ```bash
    git clone https://github.com/open-edge-platform/edge-ai-libraries.git
    cd edge-ai-libraries/microservices/time-series-analytics/docker

    # build
    docker compose build
    ```

    > **Note:**
    > To include copyleft licensed sources when building the Docker image, use the below command:
    >
    > ```bash
    > docker compose build --build-arg COPYLEFT_SOURCES=true
    > ```

2. **Clone the source and build the sample app**.

    ```bash
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal

    # build
    make build # builds only data simulator and fusion analytics docker images
    ```

    > **Note:**
    > To include copyleft licensed sources when building the Docker images, use the below command:
    >
    > ```bash
    > make build_copyleft_sources
    > ```

3. **Deploy with Docker compose and verify**.

    Follow the remaining steps/sections starting from

    [docker compose deployment](../get-started.md#deploy-with-docker-compose)
