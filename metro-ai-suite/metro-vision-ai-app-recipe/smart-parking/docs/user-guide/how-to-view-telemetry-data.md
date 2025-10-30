# View Open Telemetry Data

DL Streamer Pipeline Server supports gathering metrics over Open Telemetry. The supported metrics currently are:
- `cpu_usage_percentage`: Tracks CPU usage percentage of DL Streamer Pipeline Server python process
- `memory_usage_bytes`: Tracks memory usage in bytes of DL Streamer Pipeline Server python process
- `fps_per_pipeline`: Tracks FPS for each active pipeline instance in DL Streamer Pipeline Server

## Visualizing metrics in Prometheus

### For Docker

Open [`https://<HOST_IP>/prometheus/`](https://<HOST_IP>/prometheus/) in your browser to view the prometheus console


### For Helm

Open [`http://<HOST_IP>:30443/prometheus/`](https://<HOST_IP>:30443/prometheus/) in your browser to view the prometheus console


### Try Out the Following Queries
- `cpu_usage_percentage`
- `memory_usage_bytes`
- `fps_per_pipeline{}`
    - If you are starting multiple pipelines, then it can also be queried per pipeline ID. Example: `fps_per_pipeline{pipeline_id="658a5260f37d11ef94fc0242ac160005"}`
![Open telemetry fps_per_pipeline example in prometheus](./_images/prometheus_fps_per_pipeline.png)
