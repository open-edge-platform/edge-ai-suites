# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Formatting utilities for telemetry display."""

import math


def degrees_to_dms(decimal: float) -> str:
    """Convert decimal degrees to degrees-minutes-seconds format."""
    d = int(decimal)
    m = int((abs(decimal) - abs(d)) * 60)
    s = ((abs(decimal) - abs(d)) * 60 - m) * 60
    return f"{d}° {m}' {s:.2f}\""


def format_position_dms(lat: float, lon: float, alt: float) -> str:
    """Format position in DMS format."""
    lat_dms = degrees_to_dms(lat) + (" N" if lat >= 0 else " S")
    lon_dms = degrees_to_dms(lon) + (" E" if lon >= 0 else " W")
    return f"""GPS Position (DMS format):
Latitude:  {lat_dms}
Longitude: {lon_dms}
Altitude:  {alt:.1f} m"""


def format_position_decimal(lat: float, lon: float, alt: float) -> str:
    """Format position in decimal degrees."""
    return f"""GPS Position:
Latitude:  {lat:.6f}°
Longitude: {lon:.6f}°
Altitude:  {alt:.1f} m

Google Maps: https://www.google.com/maps?q={lat},{lon}"""


def assess_battery_health(voltage: float, remaining: float) -> str:
    """Assess battery health status."""
    if voltage > 12.0 and remaining > 80:
        return "Excellent ✓"
    elif voltage > 11.5 and remaining > 50:
        return "Good"
    elif voltage > 11.0 and remaining > 20:
        return "Low ⚠️"
    else:
        return "Critical ⛔"


def check_attitude_stability(roll_rad: float, pitch_rad: float) -> str:
    """Check if attitude is stable."""
    stable = abs(roll_rad) < 0.2 and abs(pitch_rad) < 0.2
    return "✓ Stable" if stable else "⚠️  Unstable"


def calculate_ground_speed(north_ms: float, east_ms: float) -> float:
    """Calculate ground speed from NED velocity components."""
    return math.sqrt(north_ms**2 + east_ms**2)


def calculate_total_speed(north_ms: float, east_ms: float, down_ms: float) -> float:
    """Calculate total 3D speed from NED velocity components."""
    return math.sqrt(north_ms**2 + east_ms**2 + down_ms**2)
