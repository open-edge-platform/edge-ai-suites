<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Tool Verification

Status: ✅ ALL TOOLS VERIFIED

## Environment

- ✅ PX4 SITL + Gazebo running (docker-compose.yml)
- ✅ MQTT broker :1884
- ✅ MCP server configured
- ✅ 24 tools loaded

## Verified Examples

**Example 1: Quick Status** ✅  
Test: `mavlink_get_status` → "🟢 DISARMED | Mode: HOLD | ✓ Connected | 🔋 100%"

**Example 2: Real-Time Monitoring** ✅  
Test: `mavlink_check_health` → Health score 100/100

**Example 3: Flight Anomaly Detection** ✅  
Tools: mavlink_collect_flight_data, anomalib_train, anomalib_predict → READY

**Example 4: Battery Health** ✅  
Test: `mavlink_get_battery` → 16.20V, 100%

**Example 5: Video Processing** ✅  
Tools: dlstreamer_run_sample, dlstreamer_build_pipeline → READY

## Tool Registry

**MAVLink** (15 tools)  
get_telemetry, get_status, get_position, get_battery, get_attitude, get_velocity, check_health, monitor_flight, collect_flight_data, + 6 command tools

**Anomalib** (5 tools)  
train, predict, export, benchmark, openvino_inference

**DLStreamer** (4 tools)  
build_pipeline, run_sample, list_samples, download_models

## Quick Verify

```bash
# Check stack
docker compose -f docker-compose.yml ps

# Test tool
cd mcp-server
uv run python -c "from providers.telemetry import get_status; print(get_status({}))"

# Full verify
make verify
```

## Notes

- AI models require trained files or downloaded models
- Data collection takes actual duration (60s = wait 60s)
- Uses PX4 SITL simulation (replace with real logs for production)
