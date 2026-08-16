<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MAVLink Message Discovery

## List all messages from PX4 SITL

```
Run scripts/mavlink_listener.py to connect to the MAVLink stream at
UDP :14541 and print every message type and all its fields that PX4 SITL
is emitting. I want to see the full list of available message types so I can
decide which fields to add to the telemetry overlay.
```

## Filter to a specific message type

```
Run scripts/mavlink_listener.py --filter BATTERY_STATUS to show only
battery status messages from the MAVLink stream at :14541.
Print the field names and their current values. I want to find the
correct field for battery voltage to add to the overlay.
```

## Listen on a different port

```
Run scripts/mavlink_listener.py --port 14550 to listen directly on
the PX4 SITL output port rather than the mavlink-router broadcast port.
Show all message types and fields for 30 seconds, then summarise which
message types were seen.
```

## Save messages to a file for analysis

```
Run scripts/mavlink_listener.py --output /tmp/mavlink_log.txt to capture
all incoming MAVLink messages to a file for 60 seconds while the PX4 SITL
is running. Then show me a summary of all unique message types captured
and their field names.
```

## Run the listener inside the container

```
Run the MAVLink listener inside the dlstreamer-pipeline-server container
using docker exec so it connects to the internal MAVLink stream at :14541.
Filter to show only GLOBAL_POSITION_INT and VFR_HUD messages.
```
