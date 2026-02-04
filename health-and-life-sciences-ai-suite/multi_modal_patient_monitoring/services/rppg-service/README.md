# RPPG Service

Remote Photoplethysmography (rPPG) service for contactless vital signs monitoring from facial video.

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
