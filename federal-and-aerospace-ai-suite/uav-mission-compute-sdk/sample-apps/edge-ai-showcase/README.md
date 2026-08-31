<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Intel Edge AI Showcase

Dashboard demonstrating Intel Edge AI with multi-camera UAV surveillance.

## Features

- 3-camera feeds with YOLOv2-tiny detection (nadir, forward, rear)
- Real-time performance metrics (FPS, latency)
- UAV telemetry (position, battery, altitude)
- Demo mission control (arm, takeoff, survey waypoints, land)

## Start

```bash
# Requires UAV stack running first
# From repo root:
make up

# Start dashboard
docker compose up -d
```

Open http://localhost:5002

**Verify data flow**:

- Camera feeds should appear within 10 seconds
- Detection counts should update in real-time
- FPS metrics should show ~20-30 FPS per camera

## 🔍 What You'll See

### Live Camera Feeds
Each camera shows:
- Real-time video with detection overlays
- Bounding boxes around detected vehicles
- Camera ID and inference device badge
- FPS and detection count

### Detection Analytics
- **Total Detections**: Cumulative count across all cameras
- **Coverage Area**: Estimated surveillance area based on altitude + FOV

### Performance Metrics
Side-by-side comparison:
- **GPU Inference (Nadir)**: ~45 FPS (FP16 optimized)
- **CPU Inference (Forward)**: ~28 FPS (FP32 baseline)
- **GPU INT8 (Rear)**: ~30 FPS (quantized model)

### UAV Telemetry
- **Altitude**: Height above ground (meters)
- **Position**: GPS coordinates (lat/lon)
- **Battery**: Remaining power percentage

## 🎬 Demo Scenarios

### Scenario 1: Multi-Camera Coverage
**Message**: "Single UAV, 360° coverage with 3 cameras"
- Show all 3 feeds simultaneously detecting objects
- Highlight non-overlapping coverage areas
- Demonstrate continuous surveillance

### Scenario 2: Performance Comparison
**Message**: "OpenVINO flexibility - same model, multiple devices"
- Point out FPS differences (GPU vs CPU)
- Explain FP16 vs FP32 vs INT8 trade-offs
- Show device utilization

### Scenario 3: DL Streamer Pipeline
**Message**: "Zero-copy GStreamer-based AI pipeline"
- Mention pipeline components (decode → preprocess → infer → postprocess)
- Highlight multi-model capability
- Show scalability to multiple cameras

### Scenario 4: Real-World Application
**Message**: "Production-ready edge AI for surveillance"
- Traffic monitoring
- Perimeter security
- Infrastructure inspection
- Search and rescue

## 🔧 Customization

### Add New Models
Edit `sample-apps/helpers/vision-processor/detector_multicam.py`:
```python
# Change model
MODEL_XML = "/models/your-model.xml"
MODEL_PROC = "/models/your-model.json"
```

### Adjust Performance
Edit `docker-compose.yml`:
```yaml
environment:
  - INFERENCE_DEVICE=GPU  # or CPU, NPU
  - CONF_THRESH=0.3       # Detection threshold
  - MAX_FPS=30            # Frame rate cap
```

### Enable Anomalib
Coming soon: Anomaly detection integration
```bash
# Future feature
ENABLE_ANOMALIB=true
ANOMALY_MODEL=padim
```

## 📈 Performance Benchmarks

Tested on Intel Core i7-1165G7 + Intel Iris Xe Graphics:

| Camera | Device | Model | FPS | Latency |
|--------|--------|-------|-----|---------|
| Nadir  | GPU    | FP16  | 45  | 22ms    |
| Forward| CPU    | FP32  | 28  | 35ms    |
| Rear   | GPU    | INT8  | 30  | 33ms    |

## 🐛 Troubleshooting

### No camera feeds
```bash
# Check vision processor
docker logs vision-processor-multicam --tail 20

# Restart if needed
# From repo root:
docker compose -f sample-apps/docker-compose.yml restart vision-processor
```

### Low FPS
- Check GPU is accessible: `docker run --device /dev/dri intel/dlstreamer clinfo`
- Reduce frame rate: Set `MAX_FPS=15` in compose file
- Switch to CPU: Set `INFERENCE_DEVICE=CPU`

### Dashboard not updating
```bash
# Check MQTT connection
docker logs edge-ai-showcase --tail 20

# Verify broker
docker exec mosquitto mosquitto_sub -t "uav/#" -C 3
```

## 🔗 Related Links

- [Intel DL Streamer](https://github.com/dlstreamer/dlstreamer)
- [OpenVINO Toolkit](https://github.com/openvinotoolkit/openvino)
- [Edge AI Libraries](https://github.com/open-edge-platform/edge-ai-libraries)
- [Anomalib](https://github.com/openvinotoolkit/anomalib)

## 📝 Future Enhancements

### Phase 2: Anomaly Detection
- Integrate Anomalib (PadIM, PatchCore)
- Detect unusual objects/patterns
- Anomaly heatmap overlay

### Phase 3: Multi-Model Pipeline
- Vehicle classification (ResNet)
- License plate detection
- Vehicle attributes (color, type)

### Phase 4: Advanced Analytics
- Historical detection trends
- Heatmap visualization
- Event detection & alerts

## 🎓 Educational Value

This demo is perfect for:
- **Technical Demos**: Show Edge AI capabilities to customers
- **Developer Training**: Example of production Edge AI pipeline
- **Benchmarking**: Compare models, devices, optimizations
- **Research**: Test new models/algorithms in realistic scenario

## 📄 License

Part of the FedAero UAV SDK PoC project.
