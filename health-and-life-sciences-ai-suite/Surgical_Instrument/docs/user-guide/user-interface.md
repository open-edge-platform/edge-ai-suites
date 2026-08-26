# User Interface

To open the application the GUI, go to `http://localhost:8080` in your browser.
You can change the address with `make up UI_HOST_PORT=9090` and print the LAN URL with
`make up` and `make run` to be able to open the app from a different computer in the same
network.

All on-screen data is driven by a single Server-Sent Events stream at `/api/events`
(~1 Hz snapshot). There is no client-side state polling. The rendered video appears in a
native pop-up sink launched by the pipeline container when display mode is enabled.

Here is a detailed description of the layout:

**Left column**

| Block            | Source                                                 | Notes                                                              |
|------------------|--------------------------------------------------------|--------------------------------------------------------------------|
| Source section   | local form state → `POST /api/start` payload           | Select `file` or `basler` and source argument (path / serial).     |
| Device section   | local form state → `POST /api/start` payload           | Select runtime target (`GPU` / `CPU` / `NPU`).                     |
| Session controls | `POST /api/start`, `POST /api/stop`, `POST /api/reset` | Start/Stop/Reset from the accordion instead of toolbar/modal flow. |

**Right column — Pipeline Performance accordion**

| Column   | Source                                     | Meaning                             |
|----------|--------------------------------------------|-------------------------------------|
| Workload | static                                     | `Polyp Detection`                   |
| Model    | static                                     | `yolo11n`                           |
| Device   | `pipeline_performance.workloads[0].device` | Colored pill: `GPU` / `CPU` / `NPU` |
| FPS      | `pipeline_performance.workloads[0].fps`    | Rolling mean over the last ~5 s     |
| **Mean** | `pipeline_latency.mean_ms`                 | Rolling mean pipeline latency from GST tracer samples |
| **P50**  | `pipeline_latency.p50_ms`                  | Median pipeline latency             |
| **P90**  | `pipeline_latency.p90_ms`                  | 90th percentile pipeline latency    |
| **P95**  | `pipeline_latency.p95_ms`                  | 95th percentile pipeline latency    |
| **P99**  | `pipeline_latency.p99_ms`                  | 99th percentile pipeline latency    |
| Status   | lifecycle FSM                              | `running` / `paused` / `stopped`    |

Below the table:

- **End-to-end summary bar** — pipeline FPS · sample count · uptime · source kind.
- **Model & Input block** — model name, precision (`FP16 OpenVINO IR`),
  task/dataset (`Polyp Detection` on `ColonDB`), **video source** resolution
  (e.g. `1080p H.264 (looped)`), **model input** tensor size (`640x640`), and the
  runtime **device**.

**Right column — Platform accordion**

Live CPU / GPU / NPU utilization from `intel-npu-info` and `nvidia-smi`-style samplers,
 refreshed on every SSE snapshot.
