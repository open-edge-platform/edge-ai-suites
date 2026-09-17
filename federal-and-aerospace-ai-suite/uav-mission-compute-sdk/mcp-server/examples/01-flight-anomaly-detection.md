<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Flight Anomaly Detection

Detect abnormal behavior in UAV flight data to catch issues before crashes.

## Workflow

```mermaid
flowchart LR
    A[Collect Flight Data<br/>120s] --> B[Train Anomalib<br/>PADIM model]
    B --> C[Detect Anomalies<br/>New flight]
    C --> D[Report Issues]
    
    style A fill:#e1f5ff
    style B fill:#e8f5e9
    style C fill:#e8f5e9
    style D fill:#f3e5f5
```

## Prompt

```
"Collect 2 minutes of flight data and detect any anomalies"
```

## Steps

**1. Collect flight data** → `mavlink_collect_flight_data`
- Duration: 120 seconds
- Fields: position, attitude, velocity, battery
- Output: flight_data.csv (1,200 samples @ 10 Hz)

**2. Train anomaly model** → `anomalib_train`
- Model: PADIM
- Dataset: flight_data.csv
- Output: Trained model in results/

**3. Detect anomalies** → `anomalib_predict`
- Source: new_flight.csv
- Detects: IMU drift, battery spikes, GPS drift
- Output: Anomaly report with severity

## Example Output

```
Anomalies Detected: 12 (2%)

⚠️  45-52s: Unusual roll oscillations (±5°)
⚠️  78-81s: Battery voltage drop spike
⚠️  110-115s: GPS drift detected

Recommendations:
• Recalibrate IMU (roll oscillations)
• Check battery connections (voltage spikes)
• Verify GPS antenna (drift)
```

## Real-World Value

✅ Prevents crashes by detecting IMU/battery issues early  
✅ Automates log analysis (hours → minutes)  
✅ Detects issues humans miss in raw data
