# RPPG Service

Remote Photoplethysmography (rPPG) service for contactless vital signs monitoring from facial video.

> Update: Added Quick Start, Validation Checklist, Test Scenarios, Troubleshooting, and Quick Commands for test/validation engineers.

## What This Service Does

- **Input:** Pre-recorded video file with visible face
- **Processing:** MTTS-CAN deep learning model extracts physiological signals
- **Output:** 
  - Heart Rate (HR) in beats per minute (BPM)
  - Respiration Rate (RR) in breaths per minute (BrPM)
  - Pulse and respiration waveforms for visualization

## Architecture

### Component Sources

| Component | Source | Purpose |
|-----------|--------|---------|
| Face ROI extraction | rppg-web | Preprocessing pipeline |
| MTTS-CAN model | rppg-web | Signal extraction |
| Waveform generation | rppg-web | Visualization data |
| HR/RR calculation | SDC-MM-Simulator | Clinical metrics |
| gRPC streaming | SDC-MM-Simulator | Service architecture |

### Data Flow
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Video File │ ─▶─ │  Face ROI   │ ─▶─ │  MTTS-CAN   │ ─▶─ │  HR/RR Calc │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                     │
                                                                     ▼
                                                              ┌─────────────┐
                                                              │ Aggregator  │ ─▶ Web UI / SSE
                                                              └─────────────┘
```

## Quick Start (For Test/Validation Engineers)

1) Start Aggregator
```bash
cd ~/health-ai-suite/edge-ai-suites/health-and-life-sciences-ai-suite
docker compose up -d aggregator-service
sleep 15
docker ps | grep aggregator
```

2) Start RPPG Service
```bash
cd services/rppg-service
source venv/bin/activate
python -m src.app
```
Expected logs:
```
[INFO] RPPG Service Starting
[INFO] ✓ Video found: videos/sample.mp4
[INFO] ✓ Model loaded successfully
[INFO] ✓ Connected to aggregator at localhost:50051
[INFO] Batch 1: HR=..., RR=...
```

3) View Real-Time Data (SSE)
```bash
curl -N "http://localhost:8001/events?workloads=rppg"
```
Example stream:
```json
data: {"workload_type":"rppg","payload":{"metric":"HEART_RATE","value":72.5}}
data: {"workload_type":"rppg","payload":{"metric":"RESP_RATE","value":15.2}}
```

## Validation Checklist

- Service starts: “[INFO] RPPG Service Starting”
- Video/model found and loaded
- Connected to aggregator
- Batches log HR/RR every 1–2s
- HR in 45–150 BPM, RR in 6–30 BrPM
- SSE shows continuous data

## Test Scenarios

1) Heart Rate Accuracy
```bash
python -m src.app
# Compare "Batch X: HR=..." to ground truth ±5 BPM
```

2) Data Streaming Cadence
```bash
timeout 30 curl -N "http://localhost:8001/events?workloads=rppg" | tee out.txt
wc -l out.txt  # Expect ~20–30 lines
```

3) Service Recovery (Aggregator Restart)
```bash
docker compose stop aggregator-service
python -m src.app  # Should show retries
docker compose start aggregator-service  # Should reconnect
```

## Troubleshooting (Quick)

| Problem | Symptom | Fix |
|--------|---------|-----|
| Aggregator not running | FutureTimeoutError | `docker compose up -d aggregator-service` |
| No SSE data | curl hangs | Restart aggregator, then RPPG |
| Video missing | “Video file not found” | Ensure `videos/sample.mp4` exists |
| Model missing | “Model file not found” | Ensure `models/mtts_can.hdf5` exists |
| Unrealistic HR/RR | HR ~300 | Use clear face video, good lighting |

## Quick Command Reference

```bash
# Start
docker compose up -d aggregator-service && sleep 15
cd services/rppg-service && source venv/bin/activate && python -m src.app

# Status
docker ps | grep aggregator
ps aux | grep src.app

# View SSE
curl -N "http://localhost:8001/events?workloads=rppg" | head -20

# Logs
tail -50 logs/rppg_service.log
docker logs aggregator-service --tail 50

# Restart
pkill -f "python -m src.app"
docker compose restart aggregator-service
