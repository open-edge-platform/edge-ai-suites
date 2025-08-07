# View Open Telemetry Data

DL Streamer Pipeline Server supports gathering metrics over Open Telemetry. The supported metrics currently are:
- `cpu_usage_percentage`: Tracks CPU usage percentage of DL Streamer Pipeline Server python process
- `memory_usage_bytes`: Tracks memory usage in bytes of DL Streamer Pipeline Server python process
- `fps_per_pipeline`: Tracks FPS for each active pipeline instance in DL Streamer Pipeline Server

- Open `http://<HOST_IP>:<PROMETHEUS_PORT>` in your browser to view the prometheus console and try out the below queries (`PROMETHEUS_PORT` is by default configured as 9999 by default in the `.env` file for Docker. For the Helm setup, use the respective port configured in helm/values.yml):
    - `cpu_usage_percentage`
    - `memory_usage_bytes`
    - `fps_per_pipeline{}`
        - If you are starting multiple pipelines, then it can also be queried per pipeline ID. Example: `fps_per_pipeline{pipeline_id="658a5260f37d11ef94fc0242ac160005"}`

    ![Open telemetry fps_per_pipeline example in prometheus](./images/prometheus_fps_per_pipeline.png)

## End the demonstration

Follow this procedure to stop the sample application and end this demonstration.

1. Stop the sample application with the following command.

         docker compose down -v

2. Confirm the containers are no longer running.

         docker ps
