<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Example 5: Quick Status and Location Check

## Use Case
Fast pre-flight verification - check UAV is ready and know where it is.

## User Prompt
```
What's the UAV status and where is it?
```

## MCP Tools Called

### Tool 1: `mavlink_get_status`
**Response**:
```
🟢 DISARMED | Mode: HOLD | ✓ Connected | 🔋 100%
```

### Tool 2: `mavlink_get_position`
**Response**:
```
GPS Position:
Latitude:  47.397742°
Longitude: 8.545594°
Altitude:  488.0 m

Google Maps: https://www.google.com/maps?q=47.397742,8.545594
```

## Claude's Response

> Your UAV is ready:
>
> **Status**: DISARMED (safe), HOLD mode  
> **Battery**: 100% charged  
> **Connection**: Active ✓  
> **Location**: Zurich, Switzerland  
> - GPS: 47.397742°N, 8.545594°E  
> - Altitude: 488m  
>
> Ready for flight operations.

## When to Use
- ✅ Pre-flight quick check
- ✅ Verify GPS lock
- ✅ Confirm connection
- ✅ Check battery before mission

## Alternative Prompts
- "Is the UAV ready?"
- "Check UAV"
- "Where is it?"
- "Quick status"
