# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Telemetry query handlers for MAVLink MCP tools."""

import json
import math

from .client import client
from .formatters import (
    format_position_dms,
    format_position_decimal,
    assess_battery_health,
    check_attitude_stability,
    calculate_ground_speed,
)


def get_telemetry(arguments: dict) -> str:
    """Get current uav telemetry."""
    format_type = arguments.get('format', 'full')

    try:
        raw = client.get_telemetry()

        if format_type == 'minimal':
            return f"""UAV Status: {'ARMED' if raw['armed'] else 'DISARMED'}
Mode: {raw['mode']}
Connected: {raw['connected']}
Battery: {raw['battery']['remaining_percent']:.0f}%"""

        elif format_type == 'summary':
            pos = raw['position']
            att = raw['attitude_deg']
            vel = raw['velocity_ned_m_s']
            bat = raw['battery']

            speed = calculate_ground_speed(vel['north_m_s'], vel['east_m_s'])

            return f"""UAV Telemetry Summary
{'='*50}
Status: {'ARMED ⚠️' if raw['armed'] else 'DISARMED ✓'}
Mode: {raw['mode']}
Connection: {'✓ Connected' if raw['connected'] else '✗ Disconnected'}

Position:
  Latitude:  {pos['latitude_deg']:.6f}°
  Longitude: {pos['longitude_deg']:.6f}°
  Altitude:  {pos['relative_altitude_m']:.1f} m

Attitude:
  Roll:  {att['roll_deg']:6.1f}°
  Pitch: {att['pitch_deg']:6.1f}°
  Yaw:   {att['yaw_deg']:6.1f}°

Velocity:
  Speed: {speed:.1f} m/s
  Vertical: {-vel['down_m_s']:.1f} m/s (climb rate)

Battery:
  Voltage:   {bat['voltage_v']:.2f} V
  Remaining: {bat['remaining_percent']:.0f}%

Timestamp: {raw['timestamp']}"""

        else:  # full
            return f"""Full Telemetry Data
{'='*50}
{json.dumps(raw, indent=2)}"""

    except Exception as e:
        return f"❌ Failed to get telemetry: {e}\n\nIs the MQTT broker and companion bridge running?\nStart with: docker-compose up -d"


def get_status(arguments: dict) -> str:
    """Get quick uav status."""
    try:
        raw = client.get_telemetry()

        armed_icon = "🔴 ARMED" if raw['armed'] else "🟢 DISARMED"
        conn_icon = "✓" if raw['connected'] else "✗"
        battery_pct = raw['battery']['remaining_percent']
        battery_icon = "🔋" if battery_pct > 50 else "🪫"

        return f"""{armed_icon} | Mode: {raw['mode']} | {conn_icon} Connected | {battery_icon} {battery_pct:.0f}%"""

    except Exception as e:
        return f"❌ Cannot reach uav: {e}"


def get_position(arguments: dict) -> str:
    """Get GPS position."""
    format_type = arguments.get('format', 'decimal')

    try:
        raw = client.get_telemetry()
        pos = raw['position']

        lat = pos['latitude_deg']
        lon = pos['longitude_deg']
        alt = pos['relative_altitude_m']

        if format_type == 'dms':
            return format_position_dms(lat, lon, alt)
        else:
            return format_position_decimal(lat, lon, alt)

    except Exception as e:
        return f"❌ Failed to get position: {e}"


def get_battery(arguments: dict) -> str:
    """Get battery status."""
    try:
        raw = client.get_telemetry()
        bat = raw['battery']

        voltage = bat['voltage_v']
        remaining = bat['remaining_percent']
        health = assess_battery_health(voltage, remaining)

        return f"""Battery Status:
Voltage:   {voltage:.2f} V
Remaining: {remaining:.0f}%
Health:    {health}

{'⚠️  Consider landing soon' if remaining < 30 else ''}
{'⛔ LAND IMMEDIATELY!' if remaining < 15 else ''}"""

    except Exception as e:
        return f"❌ Failed to get battery status: {e}"


def get_attitude(arguments: dict) -> str:
    """Get uav orientation."""
    units = arguments.get('units', 'degrees')

    try:
        raw = client.get_telemetry()
        att = raw['attitude_deg']

        roll = att['roll_deg']
        pitch = att['pitch_deg']
        yaw = att['yaw_deg']

        if units == 'radians':
            roll_rad = math.radians(roll)
            pitch_rad = math.radians(pitch)
            yaw_rad = math.radians(yaw)
            stability = check_attitude_stability(roll_rad, pitch_rad)
            unit = " rad"
            roll, pitch, yaw = roll_rad, pitch_rad, yaw_rad
        else:
            roll_rad = math.radians(roll)
            pitch_rad = math.radians(pitch)
            stability = check_attitude_stability(roll_rad, pitch_rad)
            unit = "°"

        return f"""UAV Attitude:
Roll:  {roll:7.2f}{unit}
Pitch: {pitch:7.2f}{unit}
Yaw:   {yaw:7.2f}{unit}

Stability: {stability}"""

    except Exception as e:
        return f"❌ Failed to get attitude: {e}"


def get_velocity(arguments: dict) -> str:
    """Get velocity vector."""
    try:
        raw = client.get_telemetry()
        vel = raw['velocity_ned_m_s']

        north = vel['north_m_s']
        east = vel['east_m_s']
        down = vel['down_m_s']

        ground_speed = calculate_ground_speed(north, east)
        total_speed = math.sqrt(north**2 + east**2 + down**2)

        return f"""Velocity Vector (NED frame):
North: {north:6.2f} m/s
East:  {east:6.2f} m/s
Down:  {down:6.2f} m/s

Ground Speed:  {ground_speed:.2f} m/s
Total Speed:   {total_speed:.2f} m/s
Vertical Rate: {-down:.2f} m/s {'↑' if down < 0 else '↓'}"""

    except Exception as e:
        return f"❌ Failed to get velocity: {e}"
