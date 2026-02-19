# How to Build from Source

This section shows how to build the Smart Route Planning Agent from source.

## Building the Images
To build the Docker image of the Smart Route Planning Agent:

1. Ensure you are in the project directory:
     ```bash
     cd edge-ai-suites/metro-ai-suite/smart-route-planning-agent/src
     ```

2. Run the following `docker compose` command:
     ```bash
     docker compose build
     ```

## Run the Application
- Run the application:
     ```bash
     docker compose up
     ```

- Ensure that the application is running by checking the container status:
     ```bash
     docker ps
     ```

- Access the application by opening your web browser and navigate to `http://<host-ip>:7864`, to view the dashboard UI.

- [OPTIONAL] To force a clean rebuild, run the following:
     ```bash
     docker compose up --build
     ```


Note:
- Ensure your `.env` is configured, especially `HOST_IP`.
