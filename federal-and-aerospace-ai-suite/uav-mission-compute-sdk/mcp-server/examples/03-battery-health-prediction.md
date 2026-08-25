<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Example 3: Battery Health Prediction

## Use Case
Predict battery degradation and estimate remaining cycles before replacement needed.

## User Prompt
```
Analyze battery performance over the last 20 flights and predict when it needs replacement
```

## Workflow

### Step 1: Collect Historical Data
**Tool**: `mavlink_collect_flight_data`
```json
{
  "duration_seconds": 3600,
  "output_file": "battery_history.csv",
  "fields": ["battery"]
}
```

**Note**: Run this after each flight to build historical dataset

### Step 2: Get Current Battery Status
**Tool**: `mavlink_get_battery`

**Response**:
```
Battery Status:
Voltage:   15.80 V (was 16.20V when new)
Remaining: 87%
Health:    Good

Note: Voltage sag detected under load
```

### Step 3: Train Prediction Model
**Tool**: `anomalib_train`
```json
{
  "model": "fastflow",
  "data_path": "battery_history.csv",
  "category": "battery_degradation"
}
```

**Output**:
```
Training Battery Health Model
=============================
Samples: 20 flights × 3,600 samples = 72,000 data points

Learning patterns:
  ✓ Voltage decay over discharge cycles
  ✓ Internal resistance increase
  ✓ Capacity fade trends

Model trained: battery_health_predictor
```

### Step 4: Predict Remaining Life
**Tool**: `anomalib_predict`
```json
{
  "model_path": "results/fastflow/battery_degradation/",
  "source": "current_battery_stats.csv"
}
```

**Results**:
```
Battery Health Prediction
=========================

Current Status:
  Voltage: 15.80V (full charge)
  Capacity: 87% of original
  Cycles: ~145 completed
  
Degradation Analysis:
  ⚠️  Voltage drop: 0.40V from new (2.5% loss)
  ⚠️  Capacity fade: 13% (faster than expected)
  ⚠️  Internal resistance: +18% (elevated)

Prediction:
  Estimated remaining cycles: 55-65 flights
  Expected lifespan: ~200 cycles total
  Current health: 72% (Good but declining)
  
Recommended action: Order replacement battery now
Reason: Lead time may be 2-3 weeks, replace before critical
```

## Claude's Response

> # Battery Health Report
>
> Your battery is showing signs of accelerated wear:
>
> ## Current Status (Flight 145)
> - **Voltage**: 15.80V (down from 16.20V new)
> - **Capacity**: 87% of original
> - **Health Score**: 72/100 (Good but declining)
>
> ## Degradation Analysis
> The AI model detected **faster-than-normal capacity fade**:
> - Expected at 145 cycles: 92% capacity
> - Actual measured: 87% capacity
> - Difference: 5% faster degradation
>
> This suggests either:
> - Frequent deep discharges (below 20%)
> - Storage at high temperatures
> - High C-rate charging
>
> ## Prediction
> Based on current degradation rate:
> - **Remaining safe flights**: 55-65 cycles
> - **Total expected lifespan**: ~200 cycles
> - **Replacement needed**: ~3-4 weeks
>
> ## Recommendations
> 1. **Order replacement now** (2-3 week lead time)
> 2. **Reduce discharge depth**: Land at 30% instead of 20%
> 3. **Monitor voltage sag**: If >0.5V drop under load, replace immediately
> 4. **Storage**: Keep at 50% charge in cool location
>
> The model caught this early - manual tracking would have missed the accelerated fade pattern.

## Real-World Impact
- **Cost savings**: Replace proactively vs emergency purchase
- **Safety**: Avoid mid-flight battery failure
- **Optimization**: Adjust usage patterns to extend life
- **Planning**: Budget for replacements in advance

## What Makes This Useful
✅ Predicts failures before they happen  
✅ Learns from flight history (not guessing)  
✅ Actionable timeline (55-65 flights remaining)  
✅ Explains WHY battery is degrading  
✅ Helps optimize charging/usage behavior
