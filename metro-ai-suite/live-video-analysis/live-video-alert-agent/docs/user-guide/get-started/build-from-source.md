# Build from Source

This guide provides step-by-step instructions for building Live Video Alert Agent Sample Application from source.

## Building the Images

To build the Docker image for `Live Video Alert Agent` application, follow these steps:

1. Ensure you are in the project directory:

   ```bash
   cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-alert-agent
   ```

2. (Optional) To include third-party copyleft source packages in the image, export the environment variable before building:

   ```bash
   export COPYLEFT_SOURCES=true
   ```

3. Run the following `docker compose` command:

   ```bash
   docker compose -f docker/docker-compose.yml build
   ```

## Run the Application

- Run the application using the following command:

  ```bash
  docker compose -f docker/docker-compose.yml up
  ```

- For NPU deployments, include the NPU override file:

  ```bash
  export OVMS_TARGET_DEVICE=NPU
  docker compose -f docker/docker-compose.yml -f docker/docker-compose.npu.yml up
  ```

  You can also run a mixed configuration (for example, GPU for VLM and NPU for LLM):

  ```bash
  export VLM_TARGET_DEVICE=GPU
  export LLM_TARGET_DEVICE=NPU
  docker compose -f docker/docker-compose.yml -f docker/docker-compose.npu.yml up
  ```

- Ensure that the application is running by checking the container status:

  ```bash
  docker ps
  ```

- Access the application by opening your web browser and navigate to `http://localhost:9000` to view the dashboard UI.

- (Optional) To force a clean rebuild run the following:

  ```bash
  docker compose -f docker/docker-compose.yml up --build
  ```

Notes:

- The default port is `9000`, but can be changed in the compose yaml.
- Use pre-converted OpenVINO IR models from the [OpenVINO organization on Hugging Face](https://huggingface.co/OpenVINO) for best compatibility. These models are optimized for OVMS and require no additional conversion.
