# Build from Source

Build the Image-Based Video Search sample application from source to customize, debug, or extend its functionality. In this guide, you will:
- Set up your development environment.
- Compile the source code and resolve dependencies.
- Generate a runnable build for local testing or deployment.

This guide is ideal for developers who want to work directly with the source code.

## Prerequisites

Before you begin, ensure the following:
- **System Requirements**: Verify your system meets the minimum requirements.
- **Dependencies Installed**:
    - **Git**: [Install Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
    - **Docker**: [Install Docker](https://docs.docker.com/engine/install/)
- **Permissions**: Confirm you have permissions to install software and modify environment configurations.

## Installing behind a proxy

1. Follow this guide to configure your Docker environment: [Use a proxy server with the Docker CLI | Docker Documentation](https://docs.docker.com/engine/cli/proxy/)
2. Pull base images:

    ```
    docker pull docker.io/library/node:23
    docker pull docker.io/library/python:3.11
    docker pull docker.io/intel/dlstreamer:2025.0.1.2-ubuntu24
    docker pull openvino/ubuntu22_dev:2024.6.0
    ```

## Steps to Build

1. **Clone the Repository**:
   - Run:
     ```bash
     git clone https://github.com/open-edge-platform/edge-ai-suites.git
     cd ./edge-ai-suites/metro-ai-suite/search-image-by-image
     ```

2. **Build Containers**:
   - Run:
     ```bash
     docker compose build
     ```

3. **Download Models**:
   - For Linux:
     ```sh
     MODELS_PATH="$(pwd)/src/dlstreamer-pipeline-server/models"

     docker run --rm \
         -v $MODELS_PATH:/output \
         openvino/ubuntu22_dev:2024.6.0 bash -c \
         "omz_downloader --name resnet-50-pytorch --output_dir models && \
          omz_converter --name resnet-50-pytorch --download_dir models --output_dir models && \
          cp -r ./models/public/resnet-50-pytorch /output"

     docker run --rm \
         -v $MODELS_PATH:/output \
         openvino/ubuntu22_dev:2024.6.0 bash -c \
         "omz_downloader --name person-vehicle-bike-detection-2004 --output_dir models && \
          omz_converter --name person-vehicle-bike-detection-2004 --download_dir models --output_dir models && \
          cp -r ./models/intel/person-vehicle-bike-detection-2004 /output"
     ```

   - For Windows:
     ```ps1
     $MODELS_PATH="$PWD\src\dlstreamer-pipeline-server\models"

     docker run --rm `
         -v ${MODELS_PATH}:/output `
         openvino/ubuntu22_dev:2024.6.0 bash -c `
         "omz_downloader --name resnet-50-pytorch --output_dir models && `
          omz_converter --name resnet-50-pytorch --download_dir models --output_dir models && `
          cp -r ./models/public/resnet-50-pytorch /output"

     docker run --rm `
         -v ${MODELS_PATH}:/output `
         openvino/ubuntu22_dev:2024.6.0 bash -c `
         "omz_downloader --name person-vehicle-bike-detection-2004 --output_dir models && `
          omz_converter --name person-vehicle-bike-detection-2004 --download_dir models --output_dir models && `
          cp -r ./models/intel/person-vehicle-bike-detection-2004 /output"
     ```

## Validation

1. **Start Containers**:
   - Run:
     ```sh
     docker compose up -d
     ```

2. **Access the Application**:
   - The App has the following endpoints:
     - Stream UI: [http://localhost:8889/stream](http://localhost:8889/stream)
     - App UI: [http://localhost:3000](http://localhost:3000)
     - Search UI: [http://localhost:9000/docs](http://localhost:9000/docs)
     - MilvusDB UI: [http://localhost:8000](http://localhost:8000)

3. **Verify Build Success**:
   - Check the logs. Look for confirmation messages indicating the microservice started successfully.

4. **Example Output**:
   - Here is an example output:
     <div align="center">
         <img src="./_images/imagesearch1.png" width="45%" style="margin-right:1rem"/>
         <img src="./_images/imagesearch2.png" width="45%" />
     </div>

## Troubleshooting

1. **Environment Configuration Issues**:
   - Verify environment variables:
     ```bash
     echo $VARIABLE_NAME
     ```

