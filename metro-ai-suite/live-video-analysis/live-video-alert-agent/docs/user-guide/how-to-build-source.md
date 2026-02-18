# How to Build Source

This guide provides step-by-step instructions for building Live Video Alert Agent Sample Application from source.

## Building the Images
To build the Docker image for `Live Video Alert` application, follow these steps:

1. Ensure you are in the project directory:
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-alert
     ```

2. Run the following `docker compose` command:
     ```bash
     docker compose build
     ```

## Run the Application
- Run the application using the following command:
     ```bash
     docker compose up
     ```

- Ensure that the application is running by checking the container status:
     ```bash
     docker ps
     ```

- Access the application by opening your web browser and navigate to `http://localhost:9000` to view the dashboard UI.

- [OPTIONAL] To force a clean rebuild run the following:
     ```bash
     docker compose up --build
     ```


Notes:
- Ensure your environment variables are configured, especially `RTSP_URL`.
- The default port is `9000`, but can be changed using the `PORT` environment variable.
