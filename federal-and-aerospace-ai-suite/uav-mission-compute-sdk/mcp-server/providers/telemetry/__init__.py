# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Telemetry provider for Edge AI Skills MCP Server.

Provides tools for reading uav telemetry data via MQTT.
Data-only — no uav control commands.
"""

from .telemetry import (
    get_telemetry,
    get_status,
    get_position,
    get_battery,
    get_attitude,
    get_velocity,
)
from .monitoring import (
    check_health,
    monitor_flight,
    collect_flight_data,
)

HANDLERS = {
    "get_telemetry": get_telemetry,
    "get_status": get_status,
    "get_position": get_position,
    "get_battery": get_battery,
    "get_attitude": get_attitude,
    "get_velocity": get_velocity,
    "check_health": check_health,
    "monitor_flight": monitor_flight,
    "collect_flight_data": collect_flight_data,
}
