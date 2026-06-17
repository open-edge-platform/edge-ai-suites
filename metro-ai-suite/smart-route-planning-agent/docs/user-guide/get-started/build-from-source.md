# Build from Source

This section shows how to build the Smart Route Planning Agent from source.

## Building the Images

To build the Docker image of the Smart Route Planning Agent:

1. Ensure you are in src directory of the project:

     ```bash
     cd edge-ai-suites/metro-ai-suite/smart-route-planning-agent/src
     ```

2. Run the following command:

     ```bash
     docker compose build
     ```

## Configure the Smart Traffic Intersection Agent Endpoints

Edit `src/data/config.json` to add the IP addresses and ports of the nodes/machines where Smart Traffic Intersection Agents are running.

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

We can add `api_hosts` for even just one instance, but please note that minimum three instances of Smart Traffic Intersection Agent is recommended for proper route planning in the application.

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
