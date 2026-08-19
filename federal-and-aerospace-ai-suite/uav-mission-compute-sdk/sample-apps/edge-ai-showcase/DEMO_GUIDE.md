<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Demo Guide

Access: http://localhost:5002

## 5-Minute Demo Flow

**1. Introduction** (30s)  
"Intel Edge AI stack running 3 UAV cameras in real-time. YOLOv2-tiny detection on Intel GPU."

**2. Show 3 camera feeds** (1m)  
Point out: nadir (down), forward (45°), rear (45°). Live bounding boxes, ~17 FPS per camera.

**3. Performance comparison** (1m)  
GPU (FP16) vs CPU (FP32) bars. "OpenVINO = write once, deploy anywhere (CPU/GPU/NPU)."

**4. Demo mission** (1m)  
Click "Start Demo Mission" → UAV arms → takeoff → camera feeds change perspective. FPS stays stable during flight.

**5. Key point**  
"Edge AI maintains real-time performance during dynamic operation. Production-ready."

## Talking Points

**Technologies**: DL Streamer (GStreamer AI pipelines), OpenVINO (GPU inference)

**Performance**: ~50 FPS combined, 3 cameras, Intel Iris Xe integrated graphics

**Use Cases**: Traffic monitoring, perimeter security, infrastructure inspection, search & rescue

## Troubleshooting

**Low FPS**: Check GPU access, set `INFERENCE_DEVICE=CPU` if needed  
**No detections**: `docker logs vision-processor-multicam --tail 20`  
**Frozen feeds**: `docker compose restart camera-bridge` (from repo root)
