# Surgical Instrument Sample App

::::{container} component_header_row
<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/health-and-life-sciences-ai-suite/Surgical_Instrument">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/health-and-life-sciences-ai-suite/Surgical_Instrument/README.md">
     Readme
  </a>
</div>
hide_directive-->

> Note!
> This application is for **reference and evaluation purposes only**. It is
  **not intended for direct use in clinical or diagnostic environments** and is not
  validated for such a purpose.
::::

The app demonstrates how Intel hardware acceleration (CPU / Intel Arc iGPU / Intel NPU) may
be applied through DL Streamer to AI-based real-time polyp detection in video presenting
an endoscopic procedure.


## User Interface

The application offers a web-based User Interface, providing information on:

- Source selection, inference device choice, and running controls.
- Pipeline Performance information.
- Model & Input details.
- Hardware utilization.

Everything on-screen is driven by the backend's `/api/events` SSE stream (~1 Hz snapshot).
There is no client-side state polling.
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
  task/dataset (`Polyp Detection` on `CVC-ColonDB`), **video source** resolution
  (e.g. `1080p H.264 (looped)`), **model input** tensor size (`640x640`), and the
  runtime **device**.

**Right column — Platform accordion**

Live CPU / GPU / NPU utilization from `intel-npu-info` and `nvidia-smi`-style samplers,
 refreshed on every SSE snapshot.



## Supporting Resources

- [Get Started](./get-started.md) – Step-by-step instructions to build and run the application
  using `make` and Docker.
- [System Requirements](./get-started/system-requirements.md) – Hardware, software, and network
  requirements, plus an overview of the AI models used by each workload.
- [How It Works](./how-it-works.md) – High-level architecture, service responsibilities, and
  data/control flows.
- [Release Notes](./release-notes.md) – Version history and known issues.


<!--hide_directive
:::{toctree}
:hidden:

Get Started <get-started.md>
Troubleshooting <troubleshooting.md>
Release Notes <release-notes.md>

:::
hide_directive-->
