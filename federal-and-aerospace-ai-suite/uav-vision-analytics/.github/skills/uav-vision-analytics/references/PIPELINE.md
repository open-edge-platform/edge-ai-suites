<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Pipeline Reference — UAV Vision Analytics

## DLSPS Configuration

DL Streamer Pipeline Server reads `/home/pipeline-server/config.json` at startup.
Pipeline definitions use `"source": "gstreamer"` which registers them under the
`user_defined_pipelines` namespace.

**Critical schema rule:** Set variant names in the `"name"` field only — do NOT
add a `"version"` field. DLSPS maps the `name` to the pipeline version internally.
REST path and MQTT topic suffix are derived from the `name` field.

- Launch path: `POST /pipelines/user_defined_pipelines/{name}`
- Status:       `GET  /pipelines/{instance_id}/status`
- Delete:       `DELETE /pipelines/{instance_id}`

The POST response body is the integer `instance_id` — save it for DELETE calls.

---

## Pipeline GStreamer String Patterns

### File source (looped video, CPU)

```
multifilesrc location=/home/pipeline-server/resources/videos/gazebo.avi loop=true
! h264parse ! decodebin3
! gvadetect device=CPU name=detection model-instance-id=instcpu0
! gvapython module=/home/pipeline-server/gvapython/telemetry-overlay-pymavlink.py
            class=DrawDynamicText function=process_frame arg=["{{OVERLAY_NAME}}-CPU"]
! gvametaconvert add-empty-results=true name=metaconvert
! gvametapublish name=destination
! appsink name=appsink
```

### File source (GPU)

```
multifilesrc location=/home/pipeline-server/resources/videos/gazebo.avi loop=true
! h264parse ! decodebin3
! gvadetect device=GPU model-instance-id=instgpu0
            inference-region=full-frame inference-interval=1
            batch-size=1 nireq=1 ie-config="GPU_THROUGHPUT_STREAMS=1"
            threshold=0.4 name=detection
! gvapython module=/home/pipeline-server/gvapython/telemetry-overlay-pymavlink.py
            class=DrawDynamicText function=process_frame arg=["{{OVERLAY_NAME}}-GPU"]
! queue
! gvametaconvert add-empty-results=true name=metaconvert
! queue ! gvafpscounter
! appsink name=destination
```

### File source (NPU)

```
multifilesrc location=/home/pipeline-server/resources/videos/gazebo.avi loop=true
! h264parse ! decodebin3
! gvadetect device=NPU model-instance-id=instnpu0
            inference-region=full-frame inference-interval=1
            batch-size=1 nireq=4 threshold=0.4 name=detection
! gvapython module=/home/pipeline-server/gvapython/telemetry-overlay-pymavlink.py
            class=DrawDynamicText function=process_frame arg=["{{OVERLAY_NAME}}-NPU"]
! queue
! gvametaconvert add-empty-results=true name=metaconvert
! queue ! gvafpscounter
! appsink name=destination
```

### RealSense source (v4l2src, CPU)

Replace `multifilesrc...! h264parse ! decodebin3` with:
```
v4l2src device=/dev/video0
! video/x-raw,format=BGR,width=640,height=480,framerate=30/1
! videoconvert
```

### RTSP source (external camera or SDK, CPU)

Replace `multifilesrc...! h264parse ! decodebin3` with:
```
rtspsrc location={{RTSP_INPUT_URL}} latency=100
! rtph264depay ! h264parse ! decodebin3
```

---

## config.json Structure

```json
{
    "config": {
        "pipelines": [
            {
                "name": "{{PIPELINE_PREFIX}}_cpu",
                "source": "gstreamer",
                "queue": {
                    "max_size_bytes": 20000000
                },
                "pipeline": {
                    "template": "{{GSTREAMER_STRING_CPU}}",
                    "parameters": {
                        "detection-properties": {
                            "element": {
                                "name": "detection",
                                "format": "element-properties"
                            }
                        }
                    }
                }
            },
            {
                "name": "{{PIPELINE_PREFIX}}_gpu",
                ...GPU variant...
            },
            {
                "name": "{{PIPELINE_PREFIX}}_npu",
                ...NPU variant...
            }
        ]
    }
}
```

For RealSense pipelines, use `{{PIPELINE_PREFIX}}_realsense_cpu` etc.
For UAVSDK nadir/forward/rear, use `nadir_camera_rtsp_cpu`, `forward_camera_rtsp_gpu`,
`rear_camera_rtsp_npu`.

---

## REST API — Starting Pipelines

### RTSP sink (pymavlink mode)

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/{{PIPELINE_PREFIX}}_cpu \
  -H "Content-Type: application/json" \
  -d '{
    "destination": {
      "metadata": {"type": "file", "path": "/tmp/results.jsonl", "format": "json-lines"},
      "frame":    {"type": "rtsp", "path": "{{RTSP_PATH}}"}
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "CPU"
      }
    }
  }' | tr -d '"')
echo "Instance ID: $INSTANCE_ID"
```

### Stopping a pipeline

```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```

### Checking pipeline status

```bash
curl http://localhost:8081/pipelines/${INSTANCE_ID}/status | python3 -m json.tool
```

### Listing all registered pipelines

```bash
curl http://localhost:8081/pipelines
```

---

## Model Path Inside Container

The model must be present at:
```
/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml
```

The `resources/` directory is bind-mounted into the container:
```yaml
volumes:
  - "./resources:/home/pipeline-server/resources"
```

---

## RTSP Output

Annotated streams are served by DLSPS on port `8555`. The path is the
`frame.path` value from the REST POST body:
- `rtsp://<host-ip>:8555/{{RTSP_PATH}}`

For UAVSDK three-camera setup:
- `rtsp://<host-ip>:8555/nadir`
- `rtsp://<host-ip>:8555/forward`
- `rtsp://<host-ip>:8555/rear`

---

## Inference Notes

- **YOLOv8n-VisDrone FP16** is the default model. Pin `ultralytics==8.4.67` for export
  (newer versions use a CumSum-based detection head that fails on GPU/NPU OpenVINO plugins).
- CPU: `model-instance-id=instcpu0`; GPU: `instgpu0`; NPU: `instnpu0`
- GPU adds: `ie-config="GPU_THROUGHPUT_STREAMS=1"`, `batch-size=1`, `nireq=1`
- NPU adds: `nireq=4` (required for NPU parallelism)
- `threshold=0.4` is recommended (default 0.5 can miss small aerial objects)
- Enable NPU: add `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so` environment variable
