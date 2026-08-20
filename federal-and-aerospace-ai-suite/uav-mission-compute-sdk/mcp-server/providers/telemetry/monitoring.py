# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Monitoring and data collection handlers for MAVLink MCP tools."""

import time
import csv
import math
from datetime import datetime
from .client import client


def check_health(arguments: dict) -> str:
    """Run health check."""
    try:
        raw = client.get_telemetry()
        bat = raw['battery']
        att = raw['attitude_deg']
        pos = raw['position']

        issues = []
        warnings = []

        # Check connection
        if not raw['connected']:
            issues.append("✗ MAVLink disconnected")

        # Check battery
        voltage = bat['voltage_v']
        remaining = bat['remaining_percent']

        if voltage < 11.0:
            issues.append("✗ Battery critically low")
        elif voltage < 11.5:
            warnings.append("⚠️  Battery low")

        if remaining < 15:
            issues.append("✗ Battery below 15%")
        elif remaining < 30:
            warnings.append("⚠️  Battery below 30%")

        # Check attitude stability
        roll_rad = math.radians(att['roll_deg'])
        pitch_rad = math.radians(att['pitch_deg'])

        if abs(roll_rad) > 0.5 or abs(pitch_rad) > 0.5:
            warnings.append("⚠️  Unstable attitude")

        # Check altitude
        if pos['absolute_altitude_m'] > 500:
            warnings.append("⚠️  High altitude")

        # Calculate health score
        health_score = 100
        health_score -= len(issues) * 30
        health_score -= len(warnings) * 10
        health_score = max(0, health_score)

        result = f"""UAV Health Check
{'='*50}
Health Score: {health_score}/100

"""

        if not issues and not warnings:
            result += "✓ All systems nominal"
        else:
            if issues:
                result += "CRITICAL ISSUES:\n"
                for issue in issues:
                    result += f"  {issue}\n"
                result += "\n"

            if warnings:
                result += "WARNINGS:\n"
                for warning in warnings:
                    result += f"  {warning}\n"

        return result

    except Exception as e:
        return f"❌ Health check failed: {e}"


def monitor_flight(arguments: dict) -> str:
    """Monitor flight for duration."""
    duration = min(300, max(1, arguments.get('duration_seconds', 10)))
    sample_rate = min(10, max(1, arguments.get('sample_rate_hz', 1)))

    try:
        samples = []
        start_time = time.time()

        while time.time() - start_time < duration:
            raw = client.get_telemetry()
            samples.append(raw)
            time.sleep(1.0 / sample_rate)

        # Calculate statistics
        altitudes = [s['position']['relative_altitude_m'] for s in samples]
        voltages = [s['battery']['voltage_v'] for s in samples]

        return f"""Flight Monitoring Report
{'='*50}
Duration: {duration} seconds
Samples:  {len(samples)}

Altitude:
  Min: {min(altitudes):.1f} m
  Max: {max(altitudes):.1f} m
  Avg: {sum(altitudes)/len(altitudes):.1f} m

Battery:
  Start: {voltages[0]:.2f} V
  End:   {voltages[-1]:.2f} V
  Drop:  {voltages[0] - voltages[-1]:.2f} V

Status: {'ARMED' if samples[-1]['armed'] else 'DISARMED'}
Mode:   {samples[-1]['mode']}"""

    except Exception as e:
        return f"❌ Monitoring failed: {e}"
    except KeyboardInterrupt:
        return "Monitoring interrupted by user"


def collect_flight_data(arguments: dict) -> str:
    """Collect telemetry to CSV."""
    output_file = arguments.get('output_file', f"flight_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    duration = arguments.get('duration_seconds', 60)
    fields = arguments.get('fields', None)

    try:
        with open(output_file, 'w', newline='') as f:
            writer = None
            samples = 0
            start_time = time.time()

            while time.time() - start_time < duration:
                raw = client.get_telemetry()
                pos = raw['position']
                att = raw['attitude_deg']
                vel = raw['velocity_ned_m_s']
                bat = raw['battery']

                # Flatten data
                flat_data = {
                    'timestamp': raw['timestamp'],
                    'armed': int(raw['armed']),
                    'lat': pos['latitude_deg'],
                    'lon': pos['longitude_deg'],
                    'alt': pos['relative_altitude_m'],
                    'roll_deg': att['roll_deg'],
                    'pitch_deg': att['pitch_deg'],
                    'yaw_deg': att['yaw_deg'],
                    'north_ms': vel['north_m_s'],
                    'east_ms': vel['east_m_s'],
                    'down_ms': vel['down_m_s'],
                    'voltage': bat['voltage_v'],
                    'battery_pct': bat['remaining_percent']
                }

                # Filter fields if specified
                if fields:
                    flat_data = {k: v for k, v in flat_data.items() if k in fields or k == 'timestamp'}

                # Write header on first row
                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=flat_data.keys())
                    writer.writeheader()

                writer.writerow(flat_data)
                samples += 1
                time.sleep(1)

        return f"""✓ Flight data collected
Output file: {output_file}
Samples:     {samples}
Duration:    {duration} seconds
Fields:      {', '.join(flat_data.keys())}

Use this data for AI training with Anomalib."""

    except Exception as e:
        return f"❌ Data collection failed: {e}"
    except KeyboardInterrupt:
        return f"Collection interrupted. Partial data saved to {output_file}"
