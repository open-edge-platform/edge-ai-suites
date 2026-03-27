# Build from Source

This guide provides step-by-step instructions for building Live Video Captioning RAG Sample Application from source.

## Building the Image

To build the Docker image for `Live Video Captioning RAG` application, follow these steps:

1. Ensure you are in the project directory:
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag
     ```

2. Run the following `docker compose` command:
     ```bash
     docker compose build
     ```

## Run the Application

- Run the application using following command:
     ```bash
     source scripts/setup_env.sh
     docker compose up
     ```

- Ensure that the application is running by checking the container status:
     ```bash
     docker ps
     ```

- Access the application by opening your web browser and navigate to `http://<host-ip>:4172 to view the dashboard UI.

- [OPTIONAL] To force a clean rebuild run the following:
     ```bash
     docker compose up --build
     ```

> **Notes:**_
> Ensure you have properly setup the environment variables by editing the `scripts/setup_env.sh` and prepare the model in place.

## Next Steps

Proceed to [Run the Application](../get-started.md#run-the-application) for more detailed instructions.