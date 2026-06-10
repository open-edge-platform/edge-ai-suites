# Get Started

Win Vision AI is a Python application for running concurrent GStreamer inference pipelines on Intel hardware (CPU / GPU / NPU) on Windows 11.

---

## Prerequisites

### Install Python and Git

Install **Python 3.12 or higher** from [the official Python website](https://www.python.org/downloads/).
Install **Git for Windows** from [the official Git website](https://git-scm.com/install/windows).

### Set Proxies (Optional)
Go to the target directory of your choice, open PowerShell and run all the terminal commands below

```powershell
$env:http_proxy  = # example: http://proxy.example.com:891
$env:https_proxy = # example: http://proxy.example.com:891
$env:no_proxy    = "localhost,127.0.0.1"
```

### Install Intel DL Streamer

Download the latest `dlstreamer-<version>-win64.exe` from the [Intel DL Streamer releases page](https://github.com/open-edge-platform/dlstreamer/releases) and follow the [Windows installation guide](https://github.com/open-edge-platform/dlstreamer/blob/main/docs/user-guide/get_started/install/install_guide_windows.md).

> **Note:** By default, DL Streamer installs to `C:\Program Files\Intel\dlstreamer`.

---

## Set Up the Application

### Clone the Suite

If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```powershell
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set manufacturing-ai-suite
cd manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai
```

### Install Python Dependencies

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

### Set Environment Variables

First, find the `gstreamer-python` install location:

```powershell
pip show gstreamer-python
```

Note the `Location` field from the output (e.g., `C:\Users\<username>\AppData\Local\Programs\Python\Python312\Lib\site-packages`), then set `PYTHONPATH` using that path:

```powershell
$env:PYTHONPATH="<gstreamer-python-location>\gstreamer_python\Lib\site-packages"
$env:PYGI_DLL_DIRS="C:\Program Files\gstreamer\1.0\msvc_x86_64\bin"
```

Verify GStreamer and DL Streamer plugins loaded correctly:

```powershell
gst-inspect-1.0 gvadetect
```

#### Camera Input (Optional)

To use a GenICam-compatible camera (e.g., Basler, Balluff, HikRobot), download the GenICam runtime DLLs and set the required environment variables.

##### Download gstgencamsrc.dll and GenICam Runtime DLLs

Run this once to download `bin\gstgencamsrc.dll` (from the Edge AI Libraries GitHub release) and the EMVA GenICam v3.1 VC120 runtime DLLs into `bin\Win64_x64\`:

```powershell
.\src\setup_genicam_runtime.ps1
```

> **Note:** If you prefer to build the gstgencamsrc plugin from source yourself, see the [src-gst-gencamsrc README (Windows)](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/dlstreamer-pipeline-server/plugins/camera/src-gst-gencamsrc/README.md#windows).

##### Set Camera Environment Variables

```powershell
# Path to your win-vision-ai clone root
$repoRoot = "<path-to-win-vision-ai-clone>"

# GenICam runtime DLLs (downloaded by setup_genicam_runtime.ps1 into bin\Win64_x64\)
$genicamRuntime = "$repoRoot\bin\Win64_x64"

# Add gstgencamsrc.dll plugin directory to GStreamer plugin search path
$env:GST_PLUGIN_PATH = "C:\Program Files\Intel\dlstreamer\bin;$repoRoot\bin"

# GenICam transport layer — set to your camera vendor's GenTL producer path, for example:
#   Basler pylon:           C:\Program Files\Basler\pylon\Runtime\x64
#   Balluff Impact Acquire: C:\Program Files\Balluff\ImpactAcquire\bin\x64
#   HikRobot MVS:           C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64
$env:GENICAM_GENTL64_PATH = "C:\Program Files\Basler\pylon\Runtime\x64"

# Extend PATH with GenICam runtime DLLs (do NOT overwrite existing PATH)
$env:PATH = "$genicamRuntime;$env:PATH"

# Always clear the GStreamer plugin registry cache before testing with a new plugin
Remove-Item "C:\Temp\gst-registry-clean.bin" -ErrorAction SilentlyContinue
$env:GST_REGISTRY_1_0 = "C:\Temp\gst-registry-clean.bin"
```

Verify the camera plugin loaded correctly:

```powershell
gst-inspect-1.0 gencamsrc
```

---

### Download MediaMTX (for RTSP / WebRTC streaming)

Required when any pipeline uses RTSP or WebRTC frame output.

Create a new directory where MediaMTX will be downloaded, then run the setup script pointing to that directory:

```powershell
New-Item -ItemType Directory -Path "<mediamtx_dir>"
python src/setup_mediamtx.py --dir <mediamtx_dir> --version v1.18.1
$env:MEDIAMTX_PATH = "<mediamtx_dir>\mediamtx.exe"
```

---

### Download a Model

If you want to download YOLO models, you can refer to the [DL Streamer download scripts](https://github.com/open-edge-platform/dlstreamer/tree/main/scripts/download_models).

```powershell
pip install ultralytics
# FP32 (default)
python src/download_models.py --model yolo11n --outdir C:/Users/<username>/models
# FP16
python src/download_models.py --model yolo11n --outdir C:/Users/<username>/models --half
# INT8
python src/download_models.py --model yolo11n --outdir C:/Users/<username>/models --int8
```

Use the exported `.xml` path in `config.yaml`.

> **Note:** You can use your own model and video of your choice. To use the example pallet defect detection model and warehouse video, download and extract them with:
> ```powershell
> wget -O pallet_defect_detection.zip "https://github.com/open-edge-platform/edge-ai-resources/raw/06bb0d621cb14a1791672552a538beddddcc4066/models/INT8/pallet_defect_detection.zip" ; Expand-Archive -Path "pallet_defect_detection.zip" -DestinationPath "models"
> wget -O warehouse.avi "https://github.com/open-edge-platform/edge-ai-resources/raw/c13b8dbf23d514c2667d39b66615bd1400cb889d/videos/warehouse.avi"
> ```
> Update the model and video paths in `config.yaml` accordingly.

---

### Configure `config.yaml`

> **Note:** The `config.yaml` file is located in the `win-vision-ai` directory of your clone (i.e., `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai/config.yaml`).

> **Note:** Use forward slashes in all YAML paths to avoid escape issues.

#### Metrics

Controls per-pipeline FPS and latency reporting.

```yaml
metrics:
  enabled: false # false = only frame count logged
  export_interval_s: 5.0
  prometheus:
    enabled: false
    port: 8000
```

When **enabled**, each pipeline logs a full stats line every interval:

```
state=PLAYING     fps_avg=30.6    fps_now=31.6    lat_avg=3.01 ms  frames=1047
```

When **disabled**, only the frame count is shown:

```
state=PLAYING     frames=121
```

##### Prometheus

When `metrics.enabled: true` and `metrics.prometheus.enabled: true`, the app starts an HTTP server and exposes a `/metrics` endpoint that Prometheus can scrape.

**Install the client library:**

```powershell
pip install prometheus_client
```

**Enable in config:**

```yaml
metrics:
  enabled: true
  export_interval_s: 5.0
  prometheus:
    enabled: true
    port: 8000 # /metrics served at http://localhost:8000/metrics
```

**Exposed gauges** (all labelled by `pipeline_id`):

| Metric                    | Description                            |
| ------------------------- | -------------------------------------- |
| `pipeline_avg_fps`        | Rolling average FPS                    |
| `pipeline_current_fps`    | Instantaneous FPS                      |
| `pipeline_avg_latency_ms` | Rolling average inference latency (ms) |
| `pipeline_frame_count`    | Total frames processed                 |
| `pipeline_running`        | `1` if PLAYING, `0` otherwise          |

#### Models

```yaml
models:
  inst0:
    type: detection # detection | classification
    model: "C:/Users/path/to/model.xml"  # replace with your downloaded/own model path
    device: CPU # CPU | GPU | NPU
    properties:
      batch_size: 1
      threshold: 0.4
```

#### Input source

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Video file**
<!--hide_directive:sync: Video hide_directive-->

```yaml
input:
  type: file # file | rtsp | camera
  url: "C:/Users/path/to/video.avi"  # replace with your downloaded/own video path
```

<!--hide_directive:::
:::{tab-item}hide_directive--> **RTSP**
<!--hide_directive:sync: RTSP hide_directive-->

Requires [installed MediaMTX](#download-mediamtx-for-rtsp--webrtc-streaming).
Start the RTSP servers:

```yaml
input:
  type: rtsp # file | rtsp | camera
  url: "rtsp://<ip>:<port>/live.sdp"
```

<!--hide_directive:::
:::{tab-item}hide_directive--> **Camera (GenICam / Basler)**
<!--hide_directive:sync: Camera hide_directive-->

Requires the camera environment variables from [Set Environment Variables](#set-environment-variables).

`serial`, `pixel-format`, `width`, and `height` are all required fields. Any additional properties are passed verbatim to the `gencamsrc` GStreamer element — add as many as your camera/driver/gencamsrc support.

```yaml
input:
  type: camera
  serial: <camera_serial_number> # required — camera serial number
  pixel-format: mono8 # required — e.g. mono8
  width: 1280 # required — frame width in pixels
  height: 720 # required — frame height in pixels
```

<!--hide_directive:::
::::hide_directive-->

#### Frame Output

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **WebRTC**
<!--hide_directive:sync: WebRTC hide_directive-->

Streams to `http://localhost:8889/front`. Open in a browser.

```yaml
output:
  frame:
    - type: webrtc
      peer_id: front
```

<!--hide_directive:::
:::{tab-item}hide_directive--> **RTSP**
<!--hide_directive:sync: RTSP hide_directive-->

Streams to `rtsp://localhost:8554/front`. Open in VLC.

```yaml
output:
  frame:
    - type: rtsp
      path: /front
```

<!--hide_directive:::
:::{tab-item}hide_directive--> **WebRTC + RTSP (both on the same pipeline)**
<!--hide_directive:sync: WebRTCnRTSP hide_directive-->

Streams to both `http://localhost:8889/front` and `rtsp://localhost:8554/front` simultaneously.

```yaml
output:
  frame:
    - type: webrtc
      peer_id: front
    - type: rtsp
      path: /front
```

<!--hide_directive:::
::::hide_directive-->

#### Metadata Output

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **MQTT**
<!--hide_directive:sync: MQTT hide_directive-->

Download the Mosquitto Windows installer from [the official Mosquitto website](https://mosquitto.org/download/) and install it.
The default install path is `C:\Program Files\mosquitto\`.
Publishes inference results to an MQTT broker. Requires Mosquitto running on port 1883.

```yaml
output:
  metadata:
    - type: mqtt
      topic: inference/front
      port: 1883
```

Start the broker before running the app:

```powershell
# Terminal 1 — start broker
cd "C:\Program Files\mosquitto"
.\mosquitto.exe -v

# Terminal 2 — subscribe to verify
# The topic passed to -t must match the topic value set in config.yaml (e.g. inference/front)
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -t inference/front -v
```

<!--hide_directive:::
:::{tab-item}hide_directive--> **File**
<!--hide_directive:sync: File hide_directive-->

Writes inference results as JSON Lines to a local file inside output directory.

```yaml
output:
  metadata:
    - type: file
      path: "output/front-inference.jsonl"
```

<!--hide_directive:::
::::hide_directive-->

#### Full Pipeline Example

```yaml
logging:
  level: INFO
  file: null

metrics:
  enabled: false

models:
  inst0:
    type: detection
    model: "C:/Users/path/to/model.xml"  # replace with your downloaded/own model path
    device: CPU
    properties:
      batch_size: 1
      threshold: 0.4

pipelines:
  front:
    input:
      type: file
      url: "C:/Users/path/to/video.avi"  # replace with your downloaded/own video path
    inference:
      model_id: inst0
    output:
      frame:
        - type: rtsp
          path: /front
      metadata:
        - type: mqtt
          topic: inference/front
          port: 1883
  back:
    input:
      type: file
      url: "C:/Users/path/to/video.avi"  # replace with your downloaded/own video path
    inference:
      model_id: inst0
    output:
      frame:
        - type: webrtc
          peer_id: back
      metadata:
        - type: file
          path: "output/back-inference.jsonl"
```

For detection models use `model_id` as `inst0`, and for classifcation models use `model_id` as `inst1`.

---

### Supported Pipeline Combinations

The following combinations are supported in basic configuration mode.

> **Important:** `input` and `inference` are **mandatory** for all pipeline combinations below.

| Frame Output  | Metadata Output |
| ------------- | --------------- |
| RTSP          | MQTT            |
| WebRTC        | MQTT            |
| RTSP + WebRTC | MQTT            |
| RTSP          | File            |
| WebRTC        | File            |
| RTSP + WebRTC | File            |
| RTSP          | MQTT + File     |
| WebRTC        | MQTT + File     |
| RTSP + WebRTC | MQTT + File     |
| RTSP          | None            |
| WebRTC        | None            |
| RTSP + WebRTC | None            |
| None          | MQTT            |
| None          | File            |
| None          | MQTT + File     |
| None          | None            |

> **Notes:**
>
> - A single pipeline can output to both RTSP and WebRTC simultaneously using a GStreamer `tee`.
> - Multiple metadata outputs (`MQTT` + `File`) can be combined on the same pipeline.
> - When no frame output is configured, the pipeline renders locally using `d3d11videosink`.

For custom element chains or combinations not listed above, use [Raw Pipeline Mode](#advanced-raw-pipeline-mode).

---

## Run the App

```powershell
python app.py config.yaml
```

On startup the app loads the config, starts MediaMTX, launches all pipelines, and prints viewer URLs:

```
[front] RTSP stream:   rtsp://localhost:8554/front
[back]  WebRTC stream: http://localhost:8889/back
```

Press **Ctrl+C** if you need to forcefully stop the application.

---

## Advanced: Raw Pipeline Mode

Pass complete GStreamer strings directly — `models` and `pipelines` sections are ignored:

```yaml
raw_pipelines:
  # Replace C:/Users/path/to/video.avi and C:/Users/path/to/detection/model.xml with your downloaded/own paths
  front: "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter  ! d3d11videosink name=sink"
  back: "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter  ! identity name=sink ! mfh264enc bitrate=2000 gop-size=15 ! h264parse ! rtspclientsink location=rtsp://localhost:8554/back"
  right: "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter ! identity name=sink ! mfh264enc bitrate=2000 gop-size=15 ! h264parse ! whipclientsink signaller::whip-endpoint=http://localhost:8889/front/whip"
  left: "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvametaconvert add-empty-results=true ! gvametapublish method=mqtt topic=inference/back address=tcp://localhost:1883 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter ! d3d11videosink name=sink"
  camera: "gencamsrc serial=12345678 pixel-format=mono8 name=src ! videoscale ! video/x-raw, width=1920,height=1080 ! videoconvert ! queue ! d3d12videosink name=sink"
```

The above pipelines are example pipelines to run with webrtc/rtsp/any sink element.

MediaMTX starts automatically when `rtspclientsink` or `whipclientsink` appears in a string.

---

## Troubleshooting

### Inference on NPU fails with `Failed to construct OpenVINOImageInference` error

To solve this error, ensure you install the latest supported Intel® NPU Driver for Windows for Intel® Core™ Ultra processors from [the official Intel website](https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html).
