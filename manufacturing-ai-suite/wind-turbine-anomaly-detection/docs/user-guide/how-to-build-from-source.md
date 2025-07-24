# Build from source

This guide provides step-by-step instructions for building the `Time Series Analytics`
microservice and `Wind Turbine Anomaly Detection` Sample Application from source.
Please follow [prerequisites](./get-started.md#configure-docker) and understand [data flow explanation](./get-started.md#data-flow-explanation)
before proceeding with the below steps.

## Steps to Build from Source

1. **Clone the source and build the `Time Series Analytics` microservice**:

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

2. **Clone the source and build the sample app**:

    ```bash
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection

    # build
    make build # builds only data simulator (OPC-UA server and MQTT publisher) docker images
    ```

    > **Note:**  
    > To include copyleft licensed sources when building the Docker images, use the below command:
    >
    > ```bash
    > make build_copyleft_sources
    > ```

2. **Docker compose deployment and Verification**:
    
    Follow the remaining steps/sections starting from [docker compose deployment](./get-started.md#deploy-with-docker-compose)