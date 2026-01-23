# How to Build Source

This guide provides step-by-step instructions for building Live Captioning Sample Application from source.

## Building the Images
To build the Docker image for `Live Captioning` application, follow these steps:

1. Ensure you are in the project directoy:
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning
     ```

2. Run the following `docker compose` command:
     ```bash
     docker compose build
     ```

## Run the Application
- Run the application using follow command:
     ```bash
     docker compose up
     ```

- Ensure that the application is running by checking the container status:
     ```bash
     docker ps
     ```

- Access the application by opening your web browser and navigate to `http://<host-ip>:4173 to view the dashboard UI.

- [OPTIONAL] To force a clean rebuild run the following:
     ```bash
     docker compose up --build
     ```


Notes:
- Ensure your `.env` is configured, especially `HOST_IP`.
