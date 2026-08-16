<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Add / Remove Telemetry Fields

## Discover available MAVLink messages first

```
I want to add new telemetry fields to the UAV vision analytics overlay.
Run scripts/mavlink_listener.py connected to UDP :14541 and show me
all the MAVLink message types and fields being emitted by the PX4 SITL.
Filter to show ATTITUDE and BATTERY_STATUS messages specifically.
```

## Add battery voltage to the overlay

```
Add battery voltage to the telemetry overlay in
gvapython/telemetry-overlay-pymavlink.py for the UAV vision analytics
pymavlink stack. The value comes from the MAVLink BATTERY_STATUS message,
field voltages[0] (in millivolts — divide by 1000 for volts).
Show it as "BAT : {voltage:.2f} V" in the overlay.
Update latest_data in MavlinkReceiver and add the label line in
process_frame(). Also show me how to restart the container to apply changes.
```

## Add roll and pitch to the overlay

```
Add roll and pitch angles to the telemetry overlay in
gvapython/telemetry-overlay-pymavlink.py. They come from the MAVLink
ATTITUDE message: msg.roll and msg.pitch (both in radians — convert
to degrees by multiplying by 57.2958). Show them as:
  ROLL  : {roll:.1f} deg
  PITCH : {pitch:.1f} deg
```

## Remove GPS coordinates for privacy

```
Remove the LAT and LON lines from the telemetry overlay in
gvapython/telemetry-overlay-pymavlink.py to avoid displaying
GPS coordinates in the video stream. Keep all other fields intact.
```

## Remove all overlay fields except altitude and speed

```
Simplify the telemetry overlay in gvapython/telemetry-overlay-pymavlink.py
to show only ALT and SPD. Remove Name, Frame, HDG, LAT, LON, and SATS.
Also remove the GPS_RAW_INT parsing block from MavlinkReceiver since
it will no longer be needed.
```
