<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Example 4: Real-Time Monitoring with Anomaly Alerts

## Use Case
Monitor UAV during live mission and get AI-powered alerts for abnormal behavior.

## User Prompt
```
Start a live monitoring session and alert me if anything unusual happens
```

## Workflow

### Step 1: Check Health Before Mission
**Tool**: `mavlink_check_health`

**Response**:
```
UAV Health Check
==================
Health Score: 100/100
✓ All systems nominal
```

### Step 2: Start Live Monitoring
**Tool**: `mavlink_monitor_flight`
```json
{
  "duration_seconds": 180,
  "sample_rate_hz": 10
}
```

Running in background, collecting 1,800 samples...

### Step 3: Real-Time Anomaly Detection
**Tool**: `anomalib_predict` (on streaming data)
```json
{
  "model_path": "results/padim/flight_telemetry/",
  "source": "stream://localhost:8000/telemetry"
}
```

### Live Results (What Claude Reports in Real-Time)

**At 0:00**:
> ✓ Mission started - all systems normal

**At 0:45**:
> ⚠️ **ALERT**: Unusual roll behavior detected
> - Roll oscillating at 3 Hz (abnormal frequency)
> - Amplitude: ±3° (higher than baseline)
> - Anomaly score: 0.87
> - Possible cause: Wind gust or motor issue
> - Status: Monitoring...

**At 1:02**:
> ✓ Roll stabilized - likely wind gust. No action needed.

**At 1:48**:
> 🔴 **CRITICAL ALERT**: Battery voltage anomaly
> - Voltage: 14.2V → 13.8V sudden drop
> - Expected: Gradual decline
> - Anomaly score: 0.94
> - **Recommendation: RTH immediately and inspect battery**

**At 2:10**:
> ⚠️ **ALERT**: GPS accuracy degraded
> - HDOP increased: 0.9 → 2.3
> - Position confidence: 85% → 68%
> - Likely cause: Entering area with buildings
> - Status: Continue to monitor, prepare for manual if needed

**At 3:00**:
> Mission complete. 3 anomalies detected (1 critical, 2 warnings).

## Post-Mission Summary

```
Real-Time Monitoring Report
===========================
Mission Duration: 180 seconds
Samples Analyzed: 1,800
Anomalies Detected: 3

Timeline:
---------
00:45 - Roll oscillations (Warning) ✓ Resolved
01:48 - Battery voltage drop (Critical) ⚠️ Needs inspection
02:10 - GPS degradation (Warning) ✓ Resolved

Critical Issues:
----------------
🔴 Battery Performance
   - Sudden voltage drop detected
   - Pattern inconsistent with normal discharge
   - Recommendation: Ground inspection required
   - Action: Do not fly until battery inspected

Performance Summary:
-------------------
✓ Flight stability: 95% nominal
✓ GPS reliability: 92% nominal (temporary degradation)
⚠️ Battery health: Requires attention

Next Steps:
-----------
1. Inspect battery connections and cells
2. Review battery charge/discharge history
3. Consider replacement if issue persists
```

## Claude's Full Report

> # Mission Monitoring Summary
>
> I monitored the 3-minute mission and detected **1 critical issue** that needs immediate attention:
>
> ## Critical Finding 🔴
> **Battery Voltage Anomaly** (1:48 into mission)
> - Sudden 0.4V drop (14.2V → 13.8V)
> - This is NOT normal discharge behavior
> - Anomaly detection model flagged with 94% confidence
>
> **What this means**:
> - Possible bad cell in battery pack
> - Could be loose connection
> - May fail suddenly in future flights
>
> **Required action**: 
> - Ground the UAV
> - Inspect battery visually and electrically
> - Do not fly until issue resolved
>
> ## Other Events
> Two minor anomalies were detected but resolved naturally:
> 1. Roll oscillations at 0:45 (wind gust)
> 2. GPS degradation at 2:10 (building interference)
>
> Both returned to normal without intervention.
>
> ## Why This Matters
> Without AI monitoring, you wouldn't notice the voltage drop pattern until:
> - Battery fails mid-flight (crash risk)
> - Manual log review hours later (too late)
>
> The model caught this in real-time, allowing safe landing and preventing potential failure.

## Real-World Impact
- **Safety**: Prevented potential crash from battery failure
- **Real-time**: Detected during flight, not post-analysis
- **Actionable**: Clear recommendations (inspect battery)
- **Context**: Distinguishes real issues from normal variations

## What Makes This Useful
✅ Live anomaly detection during flight  
✅ Alerts to critical issues immediately  
✅ Distinguishes real problems from noise  
✅ Provides mission timeline with context  
✅ Generates detailed post-flight report
