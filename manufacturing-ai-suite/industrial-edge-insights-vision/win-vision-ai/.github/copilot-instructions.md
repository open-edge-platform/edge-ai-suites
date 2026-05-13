# WinVisionAI — Developer Instructions

This file is the authoritative context document for the `WinVisionAI` application.
It lives at `.github/copilot-instructions.md` and is auto-loaded by VS Code Copilot.
Read it before extending or debugging the module.

---

## What This Module Does

`WinVisionAI` is a **standalone Python application** for running multiple
GStreamer pipelines concurrently on Intel hardware (CPU / GPU / NPU).

The caller is responsible for constructing the launch string (or relying on the
built-in `App` to do so from a YAML config). The module handles:

- Parsing and starting the GStreamer pipeline
- Monitoring state transitions via GStreamer bus messages
- Measuring per-pipeline FPS and end-to-end latency via pad probes
- Safe parallel teardown without blocking the shared GLib main loop
- YAML configuration loading and validation
- Structured logging setup (console + optional rotating file)
- Periodic metrics export to Prometheus or the log
- Embedded MediaMTX RTSP/WebRTC server (auto-downloaded)
- RTSP re-streaming via `rtspclientsink`
- WebRTC streaming via `whipclientsink` (WHIP protocol → MediaMTX)

---

## Package Layout

```
WinVisionAI/
├── .github/
│   └── copilot-instructions.md — This file (Copilot context; auto-loaded by VS Code)
├── app.py                      — App: wires config / logging / pipelines / metrics
├── config.yaml                 — Sample configuration file
├── bin/
│   ├── gstgencamsrc.dll        — Pre-built GStreamer GenICam source plugin
│   └── Win64_x64/              — GenICam VC120 runtime DLLs (populated by setup_genicam_runtime.ps1)
├── src/
│   ├── app_runner.py           — AppRunner mixin: run loop, signal handlers, callbacks
│   ├── config_loader.py        — YAML loader → validated typed dataclasses (source of truth)
│   ├── download_models.py      — CLI helper: download Ultralytics YOLO → OpenVINO export
│   ├── exceptions.py           — ConfigError, PipelineError, WinVisionAIError
│   ├── log.py                  — Root logger setup
│   ├── media_service.py        — MediaMTX process manager (download, start, stop)
│   ├── metrics_collector.py    — MetricsCollector background thread
│   ├── metrics_exporters.py    — MetricsExporter base + LogExporter + PrometheusExporter
│   ├── pipeline.py             — Pipeline class + PipelineState enum
│   ├── pipeline_manager.py     — PipelineManager (pool + shared GLib loop)
│   └── setup_genicam_runtime.ps1 — Downloads EMVA GenICam v3.1 VC120 runtime DLLs into bin\Win64_x64\
├── tests/
│   └── example.py              — Example: two parallel pipelines with callbacks
└── docs/
    └── get-started.md
```

---

## Running the App

```bash
python app.py config.yaml
```

On startup the app:
1. Loads and validates `config.yaml`
2. Configures logging
3. Starts MediaMTX if needed (see below)
4. Starts the metrics collector
5. Launches pipelines (raw mode or structured mode — see below)
6. Logs the RTSP / WebRTC viewer URL for each structured pipeline
7. Blocks until all pipelines finish or Ctrl-C is pressed

Ctrl-C wakes the wait loop **instantly** (uses `threading.Event`, not `sleep`). The signal handler only sets a flag; all cleanup runs on the main thread after the loop exits.

---

## Configuration

Config is a YAML file. Load with:

```python
from config_loader import load_config
cfg = load_config("config.yaml")
```

`load_config` validates the file and raises `FileNotFoundError` or `ConfigError`
on any structural problem, including cross-references (a pipeline referencing a
model that does not exist in `models`).

### `logging`

```yaml
logging:
  level: INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL
  format: "%(asctime)s %(levelname)-7s %(name)s — %(message)s"
  file: null           # optional path; enables a rotating file handler (10 MB × 5)
```

Parsed into `LogConfig`.

### `metrics`

```yaml
metrics:
  enabled: false
  export_interval_s: 5.0
  prometheus:
    enabled: false
    port: 8000
```

Parsed into `MetricsConfig` → `PrometheusConfig`.

### `mediamtx`

MediaMTX settings are hardcoded in `MediaMTXConfig` (in `src/config_loader.py`):

| Field | Hardcoded value | Description |
|---|---|---|
| `path` | `mediamtx` | Directory containing `mediamtx.exe` (auto-downloaded if absent) |
| `port` | `8554` | RTSP listen port |
| `webrtc_port` | `8889` | WebRTC / WHIP / WHEP port |
| `host_ip` | `localhost` | Host advertised in logged URLs |

The MediaMTX executable path must be provided via the `MEDIAMTX_PATH` environment variable before starting the app:

```powershell
$env:MEDIAMTX_PATH = "C:\path\to\mediamtx\mediamtx.exe"
```

The app will log an error and skip MediaMTX startup if the variable is not set.

- **Structured mode** — started when at least one pipeline has RTSP or WebRTC frame output enabled.
- **Raw pipeline mode** — started only when at least one raw pipeline string contains `rtspclientsink` or `whipclientsink`. Pipelines using any other sink (`d3d12videosink`, `autovideosink`, `fakesink`, …) run without MediaMTX.

### Downloading YOLO Models

> **Source:** `src/download_models.py` is adapted from
> [`open-edge-platform/dlstreamer — scripts/download_models/download_ultralytics_models.py`](https://github.com/open-edge-platform/dlstreamer/blob/master/scripts/download_models/download_ultralytics_models.py)
> (Copyright © 2018-2026 Intel Corporation, MIT License).

To download and convert a YOLO model to OpenVINO format, use `src/download_models.py`:

```bash
pip install ultralytics
mkdir C:/Users/<username>/models
python src/download_models.py --model yolo11n --outdir C:/Users/<username>/models
```

This exports the model as an OpenVINO `.xml`/`.bin` pair inside `--outdir`. Use the `.xml` path in `config.yaml`.

Optional flags:
- `--half` — FP16 precision
- `--int8` — INT8 precision

### `models`

```yaml
models:
  inst0:
    type: detection                    # detection | classification
    model: "resources/<pipeline>/models/deployment/Detection/model/model.xml"
    device: CPU                        # CPU | GPU | NPU
    properties:
      batch_size: 1
      threshold: 0.4
  inst1:
    type: classification
    model: "resources/<pipeline>/models/deployment/Classification/model/model.xml"
    device: CPU
    properties:
      batch_size: 4
```

Each key becomes a `ModelConfig`. `properties` is an unvalidated dict — any key accepted by the target GStreamer element is valid.

- Unknown `device` values log a warning and default to `CPU`.
- Invalid `type` raises `ConfigError` with a descriptive message.

### `output` (per-pipeline block)

Output is configured **per pipeline** inside the `pipelines` section. Each pipeline defines its own `output.frame` and `output.metadata`:

```yaml
output:
  frame:
    type: rtsp               # rtsp | webrtc
    path: /front             # rtsp://<host_ip>:8554/front  (rtsp only)
    # peer_id: front         # http://<host_ip>:8889/front  (webrtc only)
  metadata:
    - type: mqtt
      topic: inference/front
      port: 1883
```

Supported metadata output types: `mqtt`, `file`.

Override for a specific pipeline by adding an `output` section inside that pipeline.

#### MQTT metadata output

The `mqtt` type emits `gvametapublish method=mqtt` into the GStreamer pipeline.
The broker address is taken from the `host` field in each `metadata` entry (defaults to `localhost`).

| Field | Default | Description |
|---|---|---|
| `topic` | *(required)* | MQTT topic name, e.g. `inference/front` |
| `port` | `1883` | Broker port |

The generated GStreamer fragment:
```
gvametapublish method=mqtt topic=<topic> address=tcp://<mediamtx.host_ip>:<port>
```

#### Verifying MQTT output

Subscribe to the topic with `mosquitto_sub` to confirm messages are flowing.
Replace `<HOST_IP>` with the machine's IP address:

```powershell
# If mosquitto tools are installed locally
mosquitto_sub -h <HOST_IP> -p 1883 -t inference/front
```
### `raw_pipelines` (advanced / override mode)

```yaml
raw_pipelines:
  front: "gencamsrc serial=12345 ! videoconvert ! d3d12videosink"
  back:  "filesrc location=video.avi ! decodebin3 ! fakesink"
```

- Each key is a human-readable pipeline name (`front`, `back`, etc.).
- The value is a **complete GStreamer pipeline string** passed verbatim to `Gst.parse_launch()`.
- If **any** pipeline value is non-empty, the `models` and `pipelines` sections are **ignored entirely** — no path validation, no inference config required.
- Set all pipeline values to `""` (or omit the section) to use standard structured mode.
- MediaMTX is started automatically when `rtspclientsink` or `whipclientsink` appears in any string; other sinks need no MediaMTX.
- Legacy list format is still accepted and converted automatically (`pipeline_0`, `pipeline_1`, …).

### `pipelines` (standard / structured mode)

```yaml
pipelines:
  front:
    input:
      type: file                       # file | rtsp
      url: "resources/videos/warehouse.avi"
    inference:
      model_id: inst0                  # must reference a key in `models`
    output:
      frame:
        type: rtsp                     # rtsp | webrtc  (choose one per pipeline)
        path: /front                   # rtsp://<host_ip>:8554/front
      metadata:
        - type: mqtt
          topic: inference/front
          port: 1883
  back:
    input:
      type: file
      url: "resources/videos/anomalib_pcb_test.avi"
    inference:
      model_id: inst0
    output:
      frame:
        type: webrtc                   # this pipeline uses WebRTC
        peer_id: back                  # http://<host_ip>:8889/back
      metadata:
        - type: mqtt
          topic: inference/back
          port: 1883
```

`inference.model_id` is validated against the `models` section at load time.

> **Note:** All pipelines in the structured section launch unconditionally. The `auto_start` field is parsed for backwards compatibility but has no effect.

---

## Input Sources

| Type | GStreamer elements built |
|---|---|
| `file` | `filesrc location="..." ! decodebin3 name=src` |
| `rtsp` | `rtspsrc location="..." latency=200 name=src ! rtph264depay ! h264parse ! d3d11h264dec` |
| `camera` | `gencamsrc serial=<serial> pixel-format=mono8 width=1920 height=1080 name=src ! videoconvert` (CPU) or `... ! d3d11upload ! d3d11convert ! "video/x-raw(memory:D3D11Memory),format=NV12"` (GPU/NPU) |

RTSP auto-negotiates transport (UDP → TCP fallback). The decode chain uses D3D11 hardware decoding, producing D3D11 memory suitable for GPU/NPU inference without a copy. `latency=200` provides headroom for the jitter buffer.

Camera input (`gencamsrc`) is for GenICam-compatible industrial cameras. Requires `serial` to be set in the config.

> **Camera setup:** `bin\gstgencamsrc.dll` ships with the repo. Run `src\setup_genicam_runtime.ps1` once to populate `bin\Win64_x64\` with the required GenICam v3.1 VC120 runtime DLLs. See [docs/get-started.md — Camera Input](docs/get-started.md#camera-input-optional) for the full environment variable setup.

---

## Inference Devices

| Device | Pipeline variant |
|---|---|
| `CPU` (detection) | `gvadetect model="..." device=CPU name=detection model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter` |
| `CPU` (classification) | `gvaclassify name=classification model="..." inference-region=full-frame pre-process-config=reverse_input_channels=yes device=CPU model-instance-id=inst1 ! queue ! gvawatermark ! gvafpscounter` |
| `GPU` / `NPU` | adds `pre-process-backend=d3d11`; pipeline ends with `d3d11convert ! gvafpscounter name=fpscounter_{name}` |

GPU/NPU pipelines stay in D3D11 memory throughout. No `d3d11download` is needed because `mfh264enc` accepts D3D11 input directly.

---

## Frame Output

Each pipeline supports exactly **one** frame output type — either RTSP or WebRTC, not both simultaneously.
Configure it with a flat `frame.type` key inside each pipeline's `output` section:

```yaml
# RTSP example
output:
  frame:
    type: rtsp
    path: /front          # required for rtsp

# WebRTC example
output:
  frame:
    type: webrtc
    peer_id: front        # required for webrtc
```

The encoder chain for RTSP output:

```
mfh264enc bitrate=2000 gop-size=15 ! h264parse
```

The encoder chain for WebRTC output (`config-interval=-1` injects SPS/PPS before every IDR so the browser receiver can start decoding at any keyframe):

```
mfh264enc bitrate=2000 gop-size=15 ! h264parse config-interval=-1
```

| Output | Sink element | Viewer |
|---|---|---|
| RTSP | `rtspclientsink location=rtsp://<host>:<port>/<path>` | VLC: `rtsp://localhost:8554/front` |
| WebRTC | `whipclientsink signaller::whip-endpoint=http://<host>:<webrtc_port>/<peer_id>/whip` | Browser: `http://localhost:8889/front` |

Different pipelines can use different output types at the same time — e.g. `front` uses RTSP and `back` uses WebRTC. The app starts a **separate MediaMTX instance per protocol** (RTSP-only and/or WebRTC-only) to prevent port conflicts and avoid unintended cross-protocol access.

Viewer URLs are logged after each pipeline launches:
```
[front] RTSP stream:   rtsp://localhost:8554/front
[back] WebRTC stream: http://localhost:8889/back
```

---

## File Structure

| File | Purpose |
|---|---|
| `src/config_loader.py` | All dataclasses + YAML parsing. **Source of truth.** Validates input types, metadata output types, and cross-references between pipelines and models. |
| `src/app_runner.py` | `AppRunner` mixin inherited by `App`: `_wait_for_completion` (uses `threading.Event` for instant Ctrl-C wake), `_install_signal_handlers` (two-phase: 1st Ctrl-C = graceful, 2nd Ctrl-C = force-abort), `_on_state_change`, `_on_completed`, `_on_error` |
| `src/download_models.py` | CLI helper: download an Ultralytics YOLO model and export it to OpenVINO format. Adapted from [dlstreamer](https://github.com/open-edge-platform/dlstreamer/blob/master/scripts/download_models/download_ultralytics_models.py). |
| `src/setup_genicam_runtime.ps1` | PowerShell script: downloads EMVA GenICam Package 2018.06 and extracts the Win64 VC120 runtime DLLs into `bin\Win64_x64\`. Run once before using camera input. |
| `src/log.py` | `setup_logging(LogConfig)` — console + optional rotating file handler |
| `src/media_service.py` | `MediaService` — downloads, configures, starts/stops `mediamtx.exe` |

---

## Logging

All modules use `logging.getLogger(__name__)`. `setup_logging` is called once by `App.__init__`:

```python
from log import setup_logging
setup_logging(cfg.logging)
```

- Adds a `StreamHandler` (console) always.
- Adds a `RotatingFileHandler` (10 MB, 5 backups) when `config.file` is set.

Do not use a separate error-reporting mechanism. Route all errors and warnings through the standard logger. `logger.exception(...)` in `except` blocks automatically captures the traceback.

---

## Metrics Architecture

```
PipelineManager.list_all() → [status dicts]
        │
        ▼
MetricsCollector          (background daemon thread, interval = export_interval_s)
        │  snapshots
        ▼
MetricsExporter           (abstract base class)
        │
        ├── PrometheusExporter   — /metrics HTTP endpoint (requires prometheus_client)
        └── LogExporter          — writes to logger at DEBUG level (default / fallback)
```

### MetricsCollector lifecycle

```python
collector = MetricsCollector(manager, cfg.metrics, exporter)
collector.start()   # starts daemon thread; calls exporter.setup() first
...
collector.stop()    # signals thread, joins, calls exporter.teardown()
```

When `metrics.enabled = false` in config, `start()` is a no-op.

### Status dict keys

| Key | Type | Description |
|---|---|---|
| `id` | str | Pipeline identifier |
| `state` | str | Current `PipelineState` value |
| `frame_count` | int | Total frames processed |
| `avg_fps` | float | Rolling average FPS since first buffer |
| `current_fps` | float | FPS over the last second |
| `avg_latency_ms` | float | Mean source-to-sink latency in milliseconds |

---

## Pipeline States

```
              ┌─────────────────────────────────────────┐
              │                QUEUED                   │  (initial)
              └──────────────────┬──────────────────────┘
                                 │ PAUSED→PLAYING bus message
                                 ▼
              ┌─────────────────────────────────────────┐
              │                PLAYING                  │
              └────────┬───────────────┬────────────────┘
                       │ EOS           │ ERROR msg       │ APPLICATION/stop
                       ▼               ▼                 ▼
                   COMPLETED        ERROR             ABORTED
```

`PipelineState.is_terminal()` returns `True` for COMPLETED, ERROR, ABORTED.

State is only updated through `_set_state()` under `_state_lock`. The bus callback (`_bus_call`) is the only place states are promoted.

---

## Threading Model

| Thread | What runs there |
|---|---|
| **Main thread** | `_wait_for_completion()` loop, `stop()` cleanup sequence |
| **GLib main loop** (`glib-mainloop` daemon) | `_bus_call()`, `_force_abort()` GLib timer |
| **GStreamer streaming threads** (internal) | `_source_pad_probe()`, `_sink_pad_probe()` |
| **Teardown thread** (`pipeline-teardown-<id>`) | `_do_delete_pipeline()` — blocks on NULL transition |
| **Metrics collector** (`metrics-collector` daemon) | `MetricsCollector._collect_loop()` |
| **External / caller threads** | `create()`, `stop()`, `status()`, `list_all()`, `remove()` |

The GLib main loop is a **module-level singleton** in `pipeline_manager.py`, started once and shared by all `PipelineManager` instances. It is guarded by `_loop_lock`.

---

## Lock Discipline

Four locks exist per `Pipeline` instance. They are **never held simultaneously** — each critical section acquires at most one lock.

| Lock | Guards |
|---|---|
| `_state_lock` | `self.state` field |
| `_metrics_lock` | `_frame_count`, `_avg_fps`, `_current_fps`, `_total_latency_ms`, `_matched_latency_count`, `_avg_latency_ms`, `_start_time`, `_last_fps_*` |
| `_latency_lock` | `_latency_times` dict (pts → wall clock) |
| `_delete_lock` | one-shot teardown guard (`_deleted` bool) |

`PipelineManager._lock` guards only the `_pipelines` dict. It is **never held** while calling `pipeline.start()` or `pipeline.stop()` to prevent deadlocks with `finished_callback`.

---

## FPS Calculation

Computed inside `_sink_pad_probe()` under `_metrics_lock`:

```
avg_fps     = frame_count / (now - start_time)
current_fps = (frame_count - last_frame_count) / (now - last_fps_time)
              — updated at most once per second (delta >= 1.0 s)
```

`_start_time` is lazily initialised on the first buffer that reaches the sink probe, so warmup frames before PLAYING is confirmed are excluded.

---

## Latency Calculation

Two-probe approach keyed by `buffer.pts`:

**Source probe** (`_source_pad_probe` on the source element's `src` pad):
```python
latency_times[buf.pts] = time.monotonic()
```

**Sink probe** (`_sink_pad_probe` on the sink element's `sink` pad):
```python
source_time = latency_times.pop(buf.pts, None)
latency_ms  = (now - source_time) * 1000
avg_latency_ms = total_latency_ms / matched_latency_count
```

Note `matched_latency_count`, not `frame_count` — not every frame gets matched (e.g. `PTS == CLOCK_TIME_NONE` is silently skipped, or source probe not attached).

**30-second eviction**: `_latency_times` entries older than 30 s are purged in the source probe to prevent unbounded growth.

Metrics are disabled when no element names are provided. Do not attempt to iterate all pads as a fallback — that double-counts in branched graphs.

---

## Stop / Teardown Flow

```
caller: pipeline.stop(graceful=True, timeout_s=5.0)
  │
  ├── pipeline.send_event(Gst.Event.new_eos())
  │     GStreamer drains naturally → EOS bus message
  │       → _bus_call: COMPLETED → _delete_pipeline()
  │
  └── GLib.timeout_add(5000, _force_abort)
        (if EOS not received in time)
        _force_abort posts APPLICATION/stop message
          → _bus_call: ABORTED → _delete_pipeline()

pipeline.stop(graceful=False)
  └── _post_stop_message() immediately → APPLICATION/stop → ABORTED
```

`_delete_pipeline()` is called from `_bus_call` (GLib thread). It immediately marks `_deleted = True` under `_delete_lock`, then spawns a daemon thread (`_do_delete_pipeline`) to perform the blocking `set_state(NULL)` + `get_state()`, avoiding stalling the shared GLib loop for all other pipelines.

The bus watch is disconnected and removed before the NULL transition so no further callbacks fire on a partially-destroyed pipeline.

---

## Dynamic Pads

Source elements that expose pads lazily (e.g. `decodebin3`, `urisourcebin`) have no static `src` pad at `start()` time. When `get_static_pad("src")` returns `None`, the code falls back to connecting the `pad-added` signal:

```python
elem.connect("pad-added", self._on_dynamic_source_pad)
```

The probe is attached inside `_on_dynamic_source_pad` when the pad actually appears.

---

## Extension Points

### Add a new pipeline state
1. Add the member to `PipelineState` in `pipeline/pipeline.py`.
2. Update `is_terminal()` return value if needed.
3. Call `_set_state(PipelineState.NEW_STATE)` from `_bus_call()` on the appropriate bus message.

### Add a new bus message handler
Inside `_bus_call()` in `pipeline/pipeline.py`, add a new `elif mtype == Gst.MessageType.XXX:` branch. Keep it fast — offload any slow work to a thread.

### Add a new input type
In `_get_source_elements()` in `app.py`, add a new `if cfg.type == "xxx":` branch returning the GStreamer source fragment string. Also add `"xxx"` to `_VALID_INPUT_TYPES` in `config/loader.py`.

### Add a new inference model type
In `_build_launch_string()` in `app.py`, extend the `element` lookup dict and add any device-specific pipeline adjustments.

### Add a new frame output type
In `_build_launch_string()` in `app.py`, add a new branch inside the `if frame is not None:` block after the WebRTC `elif`. Also add `has_active_xxx()` to `FrameOutputConfig` in `config/loader.py`.

### Add a new metadata output type
In `_build_metadata_output()` in `app.py`, add a new `if cfg.type == "xxx":` branch returning a `gvametapublish` GStreamer element fragment. Also add `"xxx"` to `_VALID_METADATA_OUTPUT_TYPES` in `config/loader.py` and add any required field validation to `_parse_metadata_output()`.

### Add a new metric
1. Add counter fields in `Pipeline.__init__` under a suitable lock (usually `_metrics_lock`).
2. Update the counter in `_sink_pad_probe()` or `_source_pad_probe()` under the same lock.
3. Expose in `status()` (reads under `_metrics_lock`).

### Add a new callback
Add the parameter to `Pipeline.__init__` and `PipelineManager.create()`, store as `self._on_xxx`, invoke with `self._invoke_callback(self._on_xxx, ...)`. `_invoke_callback` wraps in `try/except` so user exceptions cannot crash the bus thread.

### Add a new config field
1. Add the field to the relevant dataclass in `config/loader.py` with a default value.
2. Parse it in the corresponding `_parse_*` function.
3. Add validation if the value is constrained.

### Add a new metrics exporter
Subclass `MetricsExporter` in `metrics/exporters.py`:

```python
class MyExporter(MetricsExporter):
    def setup(self) -> None:
        ...  # open connection, register metric definitions

    def export(self, snapshots: list[dict]) -> None:
        for snap in snapshots:
            # push snap["avg_fps"], snap["avg_latency_ms"], etc.

    def teardown(self) -> None:
        ...  # flush / close connection
```

Pass an instance to `MetricsCollector`:

```python
collector = MetricsCollector(manager, cfg.metrics, MyExporter())
```

---

## Windows 11 Compatibility

### Code differences (already handled)

| Area | Detail |
|---|---|
| `signal.SIGTERM` | Not available on Windows. Only `SIGINT` (Ctrl+C) is registered. |
| H.264 encoder | `mfh264enc` (Media Foundation) — Windows-only, accepts D3D11 memory directly. |
| H.264 decoder | `d3d11h264dec` — Windows D3D11 hardware decoder used for RTSP input. |
| USB camera | `v4l2src` is Linux-only. Use `ksvideosrc` or `mfvideosrc` on Windows (not yet implemented). |
| YAML encoding | `load_config()` opens files with `encoding="utf-8"` explicitly. |

### Environment setup on Windows 11

The following reflects the actual installed environment on this machine.

1. **GStreamer** is installed at `C:\Program Files\gstreamer\1.0\msvc_x86_64`.

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```

3. **Python dependencies** — install into your venv:
   ```powershell
   pip install -r requirements.txt
   ```

4. **PyGObject / `gi` module** — bundled by the GStreamer installer.
   `pip install gstreamer-python`
    pip show gstreamer-python - it will show the location of gstreamer-python
    get location: Location: C:\Users\intel\AppData\Local\Programs\Python\Python314\Lib\site-packages
		   set env variables:
		   $env:PYTHONPATH="C:\Users\intel\AppData\Local\Programs\Python\Python314\Lib\site-packages\gstreamer_python\Lib\site-packages"
	
5. **Required environment variables** — these must be set before running Python.
   They are already present in the system/user environment on this machine:

   ```powershell
   $env:GSTREAMER_1_0_ROOT_MSVC_X86_64 = "C:\Program Files\gstreamer\1.0\msvc_x86_64"
   $env:GST_PLUGIN_PATH = "C:\dlstreamer_dlls"
   $env:GI_TYPELIB_PATH = "C:\Program Files\gstreamer\1.0\msvc_x86_64\lib\girepository-1.0"
   $env:PYGI_DLL_DIRS = "C:\Program Files\gstreamer\1.0\msvc_x86_64\bin"
   $env:PKG_CONFIG_PATH = "C:\Program Files\gstreamer\1.0\msvc_x86_64\lib\pkgconfig"
   $env:XDG_DATA_DIRS = "C:\dlstreamer_repo\girs"
   $env:PYTHONPATH = "C:\Program Files\Python312\Lib\site-packages\gstreamer_python\Lib\site-packages"
   $env:PATH = "C:\Program Files\gstreamer\1.0\msvc_x86_64\bin;C:\dlstreamer_dlls;" + $env:PATH
   ```

   `PYGI_DLL_DIRS` is critical — without it `import gi` raises
   `ImportError: Could not deduce DLL directories`.

6. **Smoke test** — verify the GStreamer + Python binding stack before running the app:
   ```python
   import gi
   gi.require_version("Gst", "1.0")
   from gi.repository import Gst
   Gst.init(None)
   print(Gst.version_string())
   ```

7. **Intel DL Streamer** (GVA plugins) — DLLs are pre-installed at `C:\dlstreamer_dlls`.
   Run the setup script once (as Administrator) to register env variables permanently:
   ```bat
   powershell -ExecutionPolicy Bypass -File C:\dlstreamer_dlls\setup_dls_env.ps1
   ```
   Required for `gvadetect`, `gvaclassify`, `gvametapublish`, etc.

8. **Mosquitto MQTT broker** — required when any pipeline uses `type: mqtt` metadata output.

   **Install (one-time):**
   Download the Windows installer from https://mosquitto.org/download/ and run it.
   Default install path: `C:\Program Files\mosquitto\`.

   **Start the broker** (Terminal 1):
   ```powershell
   cd "C:\Program Files\mosquitto"
   .\mosquitto.exe -v
   ```
   You should see: `Opening ipv4 listen socket on port 1883.`

   The broker must be running **before** starting the app — `gvametapublish` connects at pipeline start and errors out immediately if nothing is listening.

   **Subscribe to verify output** (Terminal 2):
   ```powershell
   & "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -t inference/front -v
   # For back pipeline:
   & "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -t inference/back -v
   ```

   **Run the app** (Terminal 3):
   ```powershell
   python app.py config.yaml
   ```

### Windows path recommendations

Use forward slashes or raw strings in YAML config to avoid backslash/escape issues:

```yaml
models:
  inst0:
    model: "C:/models/detection/model.xml"   # forward slashes — safe in YAML + GStreamer

logging:
  file: "C:/logs/pipeline.log"               # forward slashes recommended
```

---

## Known Limitations / Gotchas

| Issue | Notes |
|---|---|
| **PTS must be unique and present** | Latency measurement assumes single-stream linear pipeline. Multi-stream, B-frames, or branched graphs may mis-pair entries. |
| **Ctrl-C responsiveness** | Signal handler only sets `_running=False` and fires a `threading.Event`; the actual shutdown (GStreamer, MediaMTX) runs on the main thread. This prevents re-entrancy/lock issues on Windows. |
| **Win32 IUnknown COM errors** | `_get_igpu()` uses `Get-CimInstance` via PowerShell subprocess instead of pywin32/WMI, eliminating COM noise entirely. NPU detection uses `pnputil` (no COM). |
| **Metrics disabled with no element names** | Intentional. Iterating all pads produces nonsense in non-linear graphs. |
| **`_mainloop` is never restarted** | `shutdown()` quits the loop permanently. Create a new Python process if you need to restart. |
| **`finished_callback` does not auto-remove** | Terminal pipelines stay in the manager dict. Call `manager.remove(id)` when done. |
| **Teardown thread per pipeline** | Bounded by `5 * Gst.SECOND` timeout. If GStreamer cannot reach NULL, the thread exits with a warning. |
| **User callbacks run on the bus/probe thread** | They must be non-blocking. Offload slow work (I/O, inference) to a `concurrent.futures.ThreadPoolExecutor`. |
| **RTSP source assumes H.264** | The RTSP decode chain is hardcoded to `rtph264depay ! h264parse ! d3d11h264dec`. Other codecs need a separate branch. |
| **`mfh264enc` is Windows-only** | On Linux, replace with `x264enc` or `vaapih264enc`. |
| **PrometheusExporter requires prometheus_client** | `pip install prometheus_client` before setting `prometheus.enabled: true`. Endpoint is at `http://localhost:<port>/metrics`. |
| **Camera input requires GenICam SDK** | `type: camera` uses `gencamsrc` which requires the GenICam GStreamer plugin. Set `serial` to the camera's device serial number in the pipeline config. |
| **No `SIGTERM` on Windows** | `App` only registers `SIGTERM` on non-Windows platforms. Container/service orchestrators that send `SIGTERM` require Linux. |