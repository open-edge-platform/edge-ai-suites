# Pose Estimation Service

Real-time human pose estimation using **yolo11m-pose** (COCO-17 keypoints)
with OpenVINO inference. Draws bounding boxes, confidence labels, and skeleton
overlay on the MJPEG video stream.

## Model

| Model | Keypoints | Format | Device |
|-------|-----------|--------|--------|
| yolo11m-pose (Ultralytics) | 17 (COCO) | OpenVINO IR FP16 | CPU / GPU / NPU |

## Ports

| Port | Purpose |
|------|---------|
| 8083 | Control API (start/stop/status) |
| 8085 | MJPEG video stream with skeleton overlay |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSE_3D_DEVICE` | `GPU` | OpenVINO device (`CPU`, `GPU`, `NPU`) |
| `MODEL_PATH` | `/models/3d-pose/yolo11m-pose.xml` | Path to OpenVINO IR model |
| `VIDEO_FILE` | — | Input video path or webcam index |
| `AGGREGATOR_ADDRESS` | `localhost:50051` | gRPC aggregator endpoint |