# Get Started with WinVisionAI

A Python application for running concurrent GStreamer inference pipelines on Intel hardware (CPU / GPU / NPU) on Windows.

---

## Install Python and git

Install **Python 3.12 or higher** from https://www.python.org/downloads/.
Install **Git for Windows** from https://git-scm.com/install/windows.

---

## Set Proxies (Optional)

```powershell
$env:http_proxy  = # example: http://proxy.example.com:891
$env:https_proxy = # example: http://proxy.example.com:891
$env:no_proxy    = "localhost,127.0.0.1"
```

---

## Install Intel DL Streamer

1. Download latest Dlstreamer zip for Windows from the Intel DL Streamer releases page (https://github.com/open-edge-platform/dlstreamer/releases/tag/v2026.0.0) and extract the dll files in C:\dlstreamer_dlls

2. Open PowerShell **as Administrator** and run the setup script:

```powershell
cd C:\dlstreamer_dlls
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_dls_env.ps1
```
This installs gstreamer folder inside Program Files folder.

---

## Clone the Repository

```powershell
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b main
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai
```

## Install Python Dependencies

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install gstreamer-python
```

---

## Set Environment Variables

First, find the `gstreamer-python` install location:

```powershell
pip show gstreamer-python
```

Note the `Location` field from the output (e.g., `C:\Users\<username>\AppData\Local\Programs\Python\Python312\Lib\site-packages`), then set `PYTHONPATH` using that path:

```powershell
$env:GST_PLUGIN_PATH="C:\dlstreamer_dlls"
$env:GSTREAMER_1_0_ROOT_MSVC_X86_64="C:\Program Files\gstreamer\1.0\msvc_x86_64"
$env:PYTHONPATH="<gstreamer-python-location>\gstreamer_python\Lib\site-packages"
$env:PYGI_DLL_DIRS="C:\Program Files\gstreamer\1.0\msvc_x86_64\bin"
$env:PATH = "C:\Program Files\gstreamer\1.0\msvc_x86_64\bin;C:\dlstreamer_dlls;" + $env:PATH
```

Verify GStreamer and DL Streamer plugins loaded correctly:

```powershell
gst-inspect-1.0 gvadetect
```

### Camera Input (Optional)

To use a GenICam-compatible camera (e.g., Basler, Balluff, HikRobot), download the GenICam runtime DLLs and set the required environment variables.

The `gstgencamsrc.dll` plugin is pre-built and included in the `bin\` folder — no build step is required. If you prefer to build the plugin from source yourself, see the [src-gst-gencamsrc README (Windows)](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/dlstreamer-pipeline-server/plugins/camera/src-gst-gencamsrc/README.md#windows).

#### Download GenICam Runtime DLLs

Run this once to download the EMVA GenICam v3.1 VC120 runtime DLLs into `bin\Win64_x64\`:

```powershell
.\src\setup_genicam_runtime.ps1
```

#### Set Camera Environment Variables

```powershell
# Path to your win-vision-ai clone root
$repoRoot = "<path-to-win-vision-ai-clone>"

# GenICam runtime DLLs (downloaded by setup_genicam_runtime.ps1 into bin\Win64_x64\)
$genicamRuntime = "$repoRoot\bin\Win64_x64"

# Add gstgencamsrc.dll plugin directory to GStreamer plugin search path
$env:GST_PLUGIN_PATH = "C:\dlstreamer_dlls;$repoRoot\bin"

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

If the output says `No such element or plugin 'gencamsrc'`, see [Troubleshooting → Camera: `msvcr120.dll` / `msvcp120.dll` not found](#camera-msvcr120dll--msvcp120dll-not-found).

---

## Download MediaMTX (for RTSP / WebRTC streaming)

Required when any pipeline uses RTSP or WebRTC frame output.

```powershell
python src/setup_mediamtx.py --dir <mediamtx_dir>
$env:MEDIAMTX_PATH = "<mediamtx_dir>\mediamtx.exe"
```

---

## Download a Model

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

---

## Configure `config.yaml`

Use forward slashes in all YAML paths to avoid escape issues.

### Metrics

Controls per-pipeline FPS and latency reporting.

```yaml
metrics:
  enabled: false           # false = only frame count logged
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

#### Prometheus

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
    port: 8000          # /metrics served at http://localhost:8000/metrics
```

**Exposed gauges** (all labelled by `pipeline_id`):

| Metric | Description |
|---|---|
| `pipeline_avg_fps` | Rolling average FPS |
| `pipeline_current_fps` | Instantaneous FPS |
| `pipeline_avg_latency_ms` | Rolling average inference latency (ms) |
| `pipeline_frame_count` | Total frames processed |
| `pipeline_running` | `1` if PLAYING, `0` otherwise |


### Models

```yaml
models:
  inst0:
    type: detection          # detection | classification
    model: "C:/Users/path/to/model.xml"
    device: CPU              # CPU | GPU | NPU
    properties:
      batch_size: 1
      threshold: 0.4
```

### Input source — VIDEO FILE

```yaml
input:
  type: file                       # file | rtsp | camera
  url: "C:/Users/path/to/video"
```

### Input source — RTSP

start the rtsp servers
```yaml
input:
  type: rtsp                       # file | rtsp | camera
  url: "rtsp://<ip>:<port>/live.sdp"
```

### Input source — Camera (GenICam / Basler)

Requires the camera env variables from [Set Environment Variables](#set-environment-variables).

```yaml
input:
  type: camera
  serial: <camera_serial_number>          # camera serial number
```

### Frame Output — WebRTC

Streams to `http://localhost:8889/front`. Open in a browser.

```yaml
output:
  frame:
    type: webrtc
    peer_id: front
```

### Frame Output — RTSP

Streams to `rtsp://localhost:8554/front`. Open in VLC.

```yaml
output:
  frame:
    type: rtsp
    path: /front
```

### Metadata Output — MQTT

Download the Windows installer from https://mosquitto.org/download/ and install it.
Default install path: `C:\Program Files\mosquitto\`.
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
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -t inference/front -v
```

### Metadata Output — File

Writes inference results as JSON Lines to a local file inside output directory.

```yaml
output:
  metadata:
    - type: file
      path: "output/front-inference.jsonl"
```

### Full Pipeline Example

```yaml
logging:
  level: INFO
  file: null

metrics:
  enabled: false

models:
  inst0:
    type: detection
    model: "C:/Users/path/to/model.xml"
    device: CPU
    properties:
      batch_size: 1
      threshold: 0.4

pipelines:
  front:
    input:
      type: file
      url: "C:/Users/path/to/video.avi"
    inference:
      model_id: inst0
    output:
      frame:
        type: rtsp
        path: /front
      metadata:
        - type: mqtt
          topic: inference/front
          port: 1883
  back:
    input:
      type: file
      url: "C:/Users/path/to/video.avi"
    inference:
      model_id: inst0
    output:
      frame:
        type: webrtc
        peer_id: back
      metadata:
        - type: file
          path: "output/back-inference.jsonl"
```

For detection models use model_id as inst0 and for classifcation models, you model_id as inst1

---

## Run the App

```powershell
python app.py config.yaml
```

On startup the app loads config, starts MediaMTX, launches all pipelines, and prints viewer URLs:

```
[front] RTSP stream:   rtsp://localhost:8554/front
[back]  WebRTC stream: http://localhost:8889/back
```

Press **Ctrl+C** to stop if you want to forcefully stop the application.

---

## Advanced: Raw Pipeline Mode

Pass complete GStreamer strings directly — `models` and `pipelines` sections are ignored:

```yaml
raw_pipelines:
  front: " filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvametaconvert add-empty-results=true ! gvametapublish method=file file-path=output/front-inference.jsonl ! queue ! gvawatermark ! d3d11convert ! gvafpscounter ! identity name=sink ! mfh264enc bitrate=2000 gop-size=15 ! h264parse ! whipclientsink signaller::whip-endpoint=http://localhost:8889/front/whip"
  back:  "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=NPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvametaconvert add-empty-results=true ! gvametapublish method=mqtt topic=inference/back address=tcp://localhost:1883 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter ! identity name=sink ! mfh264enc bitrate=2000 gop-size=15 ! h264parse ! rtspclientsink location=rtsp://localhost:8554/back"
  left:  "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvametaconvert add-empty-results=true ! gvametapublish method=mqtt topic=inference/back address=tcp://localhost:1883 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter ! fakesink name=sink"
  right:  "filesrc location=\"C:/Users/path/to/video.avi\" ! decodebin3 name=src ! gvadetect model=\"C:/Users/path/to/detection/model.xml\" device=GPU pre-process-backend=d3d11 name=detection model-instance-id=inst0 threshold=0.4 batch-size=1 ! queue ! gvametaconvert add-empty-results=true ! gvametapublish method=mqtt topic=inference/back address=tcp://localhost:1883 ! queue ! gvawatermark ! d3d11convert ! gvafpscounter ! d3d11videosink name=sink"
```
Above pipelines are example pipelines to run with webrtc/rtsp/any sink element

MediaMTX starts automatically when `rtspclientsink` or `whipclientsink` appears in a string.

---

## Troubleshooting

### Camera: `msvcr120.dll` / `msvcp120.dll` not found

The GenICam VC120 DLLs depend on the Visual C++ 2013 Redistributable. Verify whether the required DLLs are present:

```powershell
"msvcr120: $(Test-Path 'C:\Windows\System32\msvcr120.dll')"
"msvcp120: $(Test-Path 'C:\Windows\System32\msvcp120.dll')"
```

If either value is `False`, install the Visual C++ 2013 Redistributable:

```powershell
$url = "https://download.microsoft.com/download/2/E/6/2E61CFA4-993B-4DD4-91DA-3737CD5CD6E3/vcredist_x64.exe"
$out = "$env:TEMP\vcredist_x64_2013.exe"
Invoke-WebRequest -Uri $url -OutFile $out
Start-Process $out -ArgumentList "/install /quiet /norestart" -Wait
Write-Host "Done. msvcr120.dll now present: $(Test-Path 'C:\Windows\System32\msvcr120.dll')"
```

### Inference on NPU fails with `Failed to construct OpenVINOImageInference` error

To solve this error, ensure you install the latest supported Intel® NPU Driver for Windows from [here](https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html) for Intel® Core™ Ultra processors