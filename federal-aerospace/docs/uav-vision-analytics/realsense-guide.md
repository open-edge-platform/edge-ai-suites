# Intel RealSense — UAV Vision Analytics

## Testing the camera streams

List connected USB devices and enumerate available video devices:

```bash
lsusb
v4l2-ctl --list-devices
```

### View the RGB video stream

```bash
ffplay -f v4l2 -input_format yuyv422 -video_size 1280x720 /dev/video4
```

### View the depth stream

```bash
ffplay -f v4l2 -input_format Z16 -video_size 848x480 /dev/video0
```

> **Note:** The `Z16` format is a 16-bit depth value per pixel. `ffplay` will render it as a greyscale image.

---

## DLStreamer pipelines

Three inference pipelines are available. Only one can be active at a time because they each access the video device directly:

| Pipeline | Inference device | `device` value |
|---|---|---|
| `drone_realsense_cpu` | CPU | `CPU` |
| `drone_realsense_gpu` | GPU | `GPU` |
| `drone_realsense_npu` | NPU | `NPU` |

### Starting a pipeline

Use the Pipeline Server REST API to start a pipeline. The POST response body is the integer
`instance_id` for the running instance — save it to stop the pipeline later.

Replace `<pipeline-name>` with one of the pipeline names from the table above,
`<rtsp-stream-name>` with the desired RTSP path (e.g. `realsense`), and `device` to
the matching value for that pipeline.

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/<pipeline-name> \
  -H 'Content-Type: application/json' \
  -d '{
    "destination": {
      "metadata": {
        "type": "file",
        "path": "/tmp/results.jsonl",
        "format": "json-lines"
      },
      "frame": {
        "type": "rtsp",
        "path": "<rtsp-stream-name>"
      }
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "<CPU|GPU|NPU>"
      }
    }
  }' | tr -d '"')
echo "Instance ID: $INSTANCE_ID"
```

**Example** — start the CPU pipeline and publish the stream at `rtsp://localhost:8555/realsense`:

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/drone_realsense_cpu \
  -H 'Content-Type: application/json' \
  -d '{
    "destination": {
      "metadata": {
        "type": "file",
        "path": "/tmp/results.jsonl",
        "format": "json-lines"
      },
      "frame": {
        "type": "rtsp",
        "path": "realsense"
      }
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

To stop the pipeline:

```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```