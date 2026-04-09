# Build from Source

This guide shows how to build the Live Video Captioning RAG sample application from the source.

## Build the Image

1. Ensure you are in the project directory:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag
     ```

2. Build the Docker image:

     ```bash
     docker compose build
     ```

## Run the Application

1. Run the application:

     ```bash
     source scripts/setup_env.sh
     docker compose up
     ```

2. Ensure that the application is running by checking the container status:
     ```bash
     docker ps
     ```

3. Open your web browser to access the application. Navigate to `http://<host-ip>:4172 to view the dashboard UI.

4. [OPTIONAL] To force a clean rebuild:

     ```bash
     docker compose up --build
     ```

> **Note:** Ensure you have set up the environment variables properly by editing the `scripts/setup_env.sh` file and prepare the model in place.

## Next Steps

See [Run the Application](../get-started.md#run-the-application) for instructions.