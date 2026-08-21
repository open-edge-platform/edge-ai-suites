#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Companion Computer Bridge

Connects PX4 (MAVLink/MAVSDK) to the rest of the stack:
  - Publishes telemetry to MQTT (uav/<id>/telemetry/*)
  - Exposes a REST API on port 8080 for direct uav control
  - Also accepts commands via MQTT topic uav/<id>/command (legacy)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request
import math

from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw
import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PX4_ADDRESS           = os.getenv("PX4_ADDRESS",        "udpin://0.0.0.0:14540")
MQTT_BROKER_HOST      = os.getenv("MQTT_BROKER_HOST",   "localhost")
MQTT_BROKER_PORT      = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID              = os.getenv("UAV_ID",            "uav-1")
REST_PORT             = int(os.getenv("REST_PORT",        "8080"))
EMIT_BRIDGE_TS_NS     = os.getenv("EMIT_BRIDGE_TS_NS", "true").lower() == "true"

CONNECT_TIMEOUT_S         = 60
CONNECT_RETRY_MAX_DELAY_S = 30
TELEMETRY_LOOP_RESTART_DELAY_S = 2.0
STALE_THRESHOLD_S         = 5.0

# Outbound MQTT publish cap (Hz) — enforced by _publish_timer, one per topic.
# Independent of the MAVSDK subscription rate.
TELEMETRY_RATE_HZ = {
    "position": float(os.getenv("RATE_POSITION_HZ", "20")),
    "attitude": float(os.getenv("RATE_ATTITUDE_HZ", "30")),
    "velocity": float(os.getenv("RATE_VELOCITY_HZ", "20")),
    "gps":      float(os.getenv("RATE_GPS_HZ",      "5")),
    "battery":  float(os.getenv("RATE_BATTERY_HZ",  "2")),
    "in_air":   float(os.getenv("RATE_IN_AIR_HZ",   "4")),
}

# MAVSDK subscription rate (Hz) — asked of PX4 for every telemetry stream.
# PX4 clamps to its firmware-level native ceiling per topic (attitude ≈ 250,
# velocity ≈ 100, position ≈ 50, gps ≈ 10).
READER_RATE_HZ = float(os.getenv("READER_RATE_HZ", "1000"))

# ---------------------------------------------------------------------------
# Fast JSON — use orjson when available (10-15x faster than stdlib)
# ---------------------------------------------------------------------------
try:
    import orjson as _json_mod
    def _dumps(obj: dict) -> bytes:
        return _json_mod.dumps(obj)
except ImportError:
    def _dumps(obj: dict) -> bytes:  # type: ignore[misc]
        return json.dumps(obj).encode()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("companion_bridge")

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
uav = System()
mqtt_client: mqtt.Client | None = None
_asyncio_loop: asyncio.AbstractEventLoop | None = None
_telemetry_topic_prefix = f"uav/{UAV_ID}/telemetry/"
# Pre-built topic strings — avoids f-string allocation on every publish.
# Populated in main() once UAV_ID is known.
_TOPICS: dict[str, str] = {}
_last_status_bytes: bytes = b""

# Latest cached telemetry value per topic.
# Reader loops write here at the native PX4 rate; publish timers read from here
# at TELEMETRY_RATE_HZ.  Object identity (``is``) then serves as a zero-cost
# "new data" check — no bridge-introduced duplicates.
_latest: dict[str, dict] = {}

_state = {
    "connected": False,
    "armed":     False,
    "mode":      "UNKNOWN",
    "stale":     False,
    "flight_time_s": 0.0,
    "timestamp": None,
}
_flight_start_time: float | None = None
_last_armed_state:  bool  = False
_last_position_mono: float = 0.0

# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------

_command_queue: asyncio.Queue | None = None


def setup_mqtt(loop: asyncio.AbstractEventLoop) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"companion-bridge-{UAV_ID}",
    )

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info("MQTT connected to %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
            client.subscribe(f"uav/{UAV_ID}/command")
        else:
            log.error("MQTT connection failed: %s", reason_code)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        log.warning("MQTT disconnected (rc=%s)", reason_code)

    def on_message(client, userdata, msg):
        if f"uav/{UAV_ID}/command" not in msg.topic:
            return
        try:
            payload = json.loads(msg.payload.decode())
            action  = payload.get("action", "")
            cid     = payload.get("id", "")
            log.info("MQTT command: %s (id=%s)", action, cid)
            if _command_queue is not None:
                loop.call_soon_threadsafe(_command_queue.put_nowait, (action, cid))
        except Exception as e:
            log.warning("Failed to parse MQTT command: %s", e)

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.loop_start()
    return client


def publish(topic_suffix: str, payload: dict) -> bool:
    """Publish to MQTT.  Rate is controlled by _publish_timer, not here.

    Returns True if the message was sent.
    """
    if not (mqtt_client and mqtt_client.is_connected()):
        return False

    if EMIT_BRIDGE_TS_NS:
        payload = {**payload, "bridge_ts_ns": time.time_ns()}

    topic = _TOPICS.get(topic_suffix) or f"{_telemetry_topic_prefix}{topic_suffix}"
    mqtt_client.publish(topic, _dumps(payload), qos=0)
    return True


async def _publish_timer(topic: str, hz: float) -> None:
    """Publish _latest[topic] at up to *hz* Hz, dropping bridge-introduced duplicates.

    Each reader-loop iteration stores a *freshly constructed* dict into _latest,
    so object identity (``is``) uniquely identifies a MAVSDK event.  If the same
    object is still in _latest on the next tick, no new MAVSDK reading has
    arrived — skip the publish.  Legitimate content-duplicates (uav hovering,
    identical values across readings) are *not* dropped because the reader always
    produces a new dict object regardless of whether the values changed.

    Uses an absolute-deadline scheduler so asyncio.sleep jitter doesn't drift.
    """
    interval = 1.0 / hz
    loop = asyncio.get_running_loop()
    next_pub = loop.time() + interval
    last_payload: dict | None = None
    while True:
        delay = next_pub - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        next_pub += interval
        payload = _latest.get(topic)
        if payload is not None and payload is not last_payload:
            publish(topic, payload)
            last_payload = payload


_last_status_bytes: bytes = b""

def publish_status():
    """Publish status only when content changes."""
    global _last_status_bytes
    if not (mqtt_client and mqtt_client.is_connected()):
        return
    payload = _dumps({
        "connected":     _state["connected"],
        "armed":         _state["armed"],
        "mode":          _state["mode"],
        "stale":         _state["stale"],
        "flight_time_s": _state["flight_time_s"],
        "timestamp":     _state["timestamp"],
    })
    if payload == _last_status_bytes:
        return
    _last_status_bytes = payload
    topic = _TOPICS.get("status") or f"{_telemetry_topic_prefix}status"
    mqtt_client.publish(topic, payload, qos=0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# REST API (Flask, runs in a daemon thread)
# ---------------------------------------------------------------------------

rest_app = Flask("companion-bridge-rest")


async def _run_action(action: str, **kwargs):
    """Execute a uav action on the asyncio loop. Returns (ok, message)."""
    if action == "arm":
        await uav.action.arm()
    elif action == "hold":
        await uav.action.hold()
    elif action == "reboot":
        await uav.action.reboot()
    elif action == "disarm":
        await uav.action.disarm()
    elif action == "kill":
        await uav.action.kill()
    elif action == "takeoff":
        alt = kwargs.get("altitude", 5.0)
        await uav.action.set_takeoff_altitude(alt)
        await uav.action.takeoff()
    elif action == "land":
        await uav.action.land()
    elif action == "return":
        await uav.action.return_to_launch()
    elif action == "goto":
        north = float(kwargs["north"])
        east = float(kwargs["east"])
        alt = -float(kwargs.get("down", -5.0))
        # Convert NED offset to absolute GPS using home position
        home_lat = _state.get("home_lat")
        home_lon = _state.get("home_lon")
        home_alt = _state.get("home_alt_msl")
        if home_lat is None:
            raise RuntimeError("Home position not yet known")
        lat = home_lat + north / 111_320.0
        lon = home_lon + east / (111_320.0 * math.cos(math.radians(home_lat)))
        abs_alt = home_alt + alt
        # NaN yaw = keep current heading
        await uav.action.goto_location(lat, lon, abs_alt, float('nan'))
    else:
        raise ValueError(f"Unknown action: {action}")


def _dispatch(action: str, **kwargs) -> tuple[bool, str]:
    """Call from any thread — schedules the coroutine on the asyncio loop and waits."""
    if _asyncio_loop is None:
        return False, "Bridge not ready"
    if not _state.get("connected"):
        return False, "UAV not connected"
    try:
        future = asyncio.run_coroutine_threadsafe(_run_action(action, **kwargs), _asyncio_loop)
        future.result(timeout=15)
        return True, "ok"
    except asyncio.TimeoutError:
        log.warning("REST command '%s' timed out", action)
        return False, "Command timed out"
    except Exception:
        log.exception("REST command '%s' failed", action)
        return False, "Command failed"


@rest_app.route("/health")
def rest_health():
    return jsonify({
        "status":    "ok",
        "connected": _state.get("connected", False),
        "armed":     _state.get("armed",     False),
        "mode":      _state.get("mode",      "UNKNOWN"),
    })


@rest_app.route("/action/<action>", methods=["POST"])
def rest_action(action: str):
    log.info("REST command: %s", action)
    body = request.get_json(silent=True) or {}
    ok, msg = _dispatch(action, **body)
    return jsonify({"success": ok, "error": msg if not ok else None}), (200 if ok else 500)


@rest_app.route("/telemetry")
def rest_telemetry():
    return jsonify(_state)


@rest_app.route("/state", methods=["GET", "POST"])
def rest_state():
    """Backward-compatible endpoint for clients expecting /state."""
    return jsonify({
        "success": True,
        "state": _state,
    })


def _start_rest_server():
    log.info("REST API listening on port %d", REST_PORT)
    try:
        # waitress: multi-threaded WSGI server — handles concurrent REST calls
        # without blocking when _dispatch() waits on the asyncio loop.
        from waitress import serve
        serve(rest_app, host="0.0.0.0", port=REST_PORT, threads=4, _quiet=True)
    except ImportError:
        # Fallback to Flask dev server (single-threaded, adequate for low load)
        log.warning("waitress not installed — using Flask dev server (single-threaded)")
        rest_app.run(host="0.0.0.0", port=REST_PORT, debug=False, use_reloader=False)


# ---------------------------------------------------------------------------
# PX4 Connection
# ---------------------------------------------------------------------------

async def connect_to_px4() -> bool:
    delay = 1.0
    while True:
        log.info("Connecting to PX4 on %s ...", PX4_ADDRESS)
        try:
            await uav.connect(system_address=PX4_ADDRESS)
            log.info("Waiting for PX4 heartbeat ...")
            elapsed = 0
            async for state in uav.core.connection_state():
                if state.is_connected:
                    log.info("Connected to PX4")
                    _state["connected"] = True
                    publish_status()
                    return True
                elapsed += 1
                if elapsed > CONNECT_TIMEOUT_S:
                    break
                await asyncio.sleep(1)
            log.warning("Connection timed out after %ds", CONNECT_TIMEOUT_S)
        except Exception:
            log.exception("Connection error")

        _state["connected"] = False
        log.info("Retrying in %.0fs ...", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, CONNECT_RETRY_MAX_DELAY_S)


async def configure_telemetry_rates():
    # Ask PX4 (via MAVSDK) to stream every topic at READER_RATE_HZ.The outbound
    # MQTT rate is enforced separately by _publish_timer using TELEMETRY_RATE_HZ.
    setters = [
        ("position", uav.telemetry.set_rate_position),
        ("attitude", uav.telemetry.set_rate_attitude_euler),
        ("velocity", uav.telemetry.set_rate_velocity_ned),
        ("gps",      uav.telemetry.set_rate_gps_info),
        ("battery",  uav.telemetry.set_rate_battery),
        ("in_air",   uav.telemetry.set_rate_in_air),
    ]
    for name, setter in setters:
        pub_hz = TELEMETRY_RATE_HZ.get(name, 20.0)
        try:
            await setter(READER_RATE_HZ)
            log.info(
                "Telemetry rate configured: %s reader=%.0f Hz (requested) publish_cap=%.1f Hz",
                name, READER_RATE_HZ, pub_hz,
            )
        except Exception:
            log.exception("Failed to set telemetry rate for %s", name)


# ---------------------------------------------------------------------------
# Telemetry loops
# ---------------------------------------------------------------------------

async def _supervised(name: str, coro_fn):
    while True:
        try:
            await coro_fn()
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Loop '%s' crashed — restarting", name)
            await asyncio.sleep(TELEMETRY_LOOP_RESTART_DELAY_S)


_INT32_MIN_M = -2147483.0


def _is_valid_position(pos) -> bool:
    return (
        pos.relative_altitude_m > _INT32_MIN_M
        and abs(pos.latitude_deg)  > 0.001
        and abs(pos.longitude_deg) > 0.001
    )


async def _position_loop():
    global _last_position_mono
    async for pos in uav.telemetry.position():
        if not _is_valid_position(pos):
            continue
        _state["timestamp"] = _now_iso()
        _state["stale"]     = False
        _last_position_mono = time.monotonic()
        if "home_lat" not in _state:
            _state["home_lat"] = pos.latitude_deg
            _state["home_lon"] = pos.longitude_deg
            _state["home_alt_msl"] = pos.absolute_altitude_m
            log.info("Home position initialized")
        _latest["position"] = {
            "reader_ts_ns":          time.time_ns(),
            "latitude_deg":          pos.latitude_deg,
            "longitude_deg":         pos.longitude_deg,
            "absolute_altitude_m":   pos.absolute_altitude_m,
            "relative_altitude_m":   pos.relative_altitude_m,
        }


async def _attitude_loop():
    async for att in uav.telemetry.attitude_euler():
        _latest["attitude"] = {
            "reader_ts_ns": time.time_ns(),
            "roll_deg":  att.roll_deg,
            "pitch_deg": att.pitch_deg,
            "yaw_deg":   att.yaw_deg,
        }


async def _battery_loop():
    async for bat in uav.telemetry.battery():
        _latest["battery"] = {
            "reader_ts_ns":       time.time_ns(),
            "voltage_v":          bat.voltage_v,
            "remaining_percent":  bat.remaining_percent,
        }


async def _velocity_loop():
    async for vel in uav.telemetry.velocity_ned():
        _latest["velocity"] = {
            "reader_ts_ns": time.time_ns(),
            "north_m_s":    vel.north_m_s,
            "east_m_s":     vel.east_m_s,
            "down_m_s":     vel.down_m_s,
        }


async def _flight_mode_loop():
    async for fm in uav.telemetry.flight_mode():
        _state["mode"] = str(fm).split(".")[-1]
        publish_status()


async def _gps_loop():
    async for info in uav.telemetry.gps_info():
        _latest["gps"] = {
            "reader_ts_ns":   time.time_ns(),
            "num_satellites": info.num_satellites,
            "fix_type":       str(info.fix_type).split(".")[-1],
        }


async def _armed_loop():
    global _flight_start_time, _last_armed_state
    async for armed in uav.telemetry.armed():
        _state["armed"] = armed
        if armed and not _last_armed_state:
            _flight_start_time = time.monotonic()
            log.info("UAV ARMED")
        elif not armed and _last_armed_state:
            _flight_start_time = None
            _state["flight_time_s"] = 0.0
            log.info("UAV DISARMED")
        elif armed and _flight_start_time is not None:
            _state["flight_time_s"] = time.monotonic() - _flight_start_time
        _last_armed_state = armed
        publish_status()


async def _connection_watchdog():
    try:
        async for state in uav.core.connection_state():
            was_connected      = _state["connected"]
            _state["connected"] = state.is_connected
            if was_connected and not state.is_connected:
                log.warning("PX4 connection lost")
                publish_status()
            elif not was_connected and state.is_connected:
                log.info("PX4 connection restored")
                publish_status()
    except Exception:
        log.exception("Connection watchdog error")


async def _staleness_watchdog():
    while True:
        await asyncio.sleep(1.0)
        if _last_position_mono and (time.monotonic() - _last_position_mono) > STALE_THRESHOLD_S:
            if not _state["stale"]:
                _state["stale"] = True
                publish_status()


# ---------------------------------------------------------------------------
# MQTT command loop (legacy — kept for compatibility)
# ---------------------------------------------------------------------------

async def _command_loop():
    while True:
        action, cid = await _command_queue.get()
        result = "ok"
        try:
            await _run_action(action)
        except Exception as e:
            result = str(e)
            log.error("Command '%s' failed: %s", action, e)
        if mqtt_client:
            mqtt_client.publish(
                f"uav/{UAV_ID}/command/result",
                json.dumps({"id": cid, "action": action, "result": result}),
                qos=1,
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_TELEMETRY_LOOPS = [
    ("position",    _position_loop),
    ("attitude",    _attitude_loop),
    ("battery",     _battery_loop),
    ("velocity",    _velocity_loop),
    ("flight_mode", _flight_mode_loop),
    ("armed",       _armed_loop),
    ("gps",         _gps_loop),
]


async def main():
    global mqtt_client, _command_queue, _asyncio_loop

    log.info("=" * 60)
    log.info("Companion Bridge Starting")
    log.info("  PX4 address : %s", PX4_ADDRESS)
    log.info("  MQTT broker : %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    log.info("  REST API    : 0.0.0.0:%d", REST_PORT)
    log.info("  UAV ID    : %s", UAV_ID)
    log.info("  Rate caps   : %s", {k: f"{v}Hz" for k, v in TELEMETRY_RATE_HZ.items()})
    log.info("=" * 60)

    # Pre-build all topic strings once to avoid per-message f-string allocation
    _TOPICS.update({
        name: f"uav/{UAV_ID}/telemetry/{name}"
        for name in ["position", "attitude", "battery", "velocity",
                     "status", "gps", "flight_mode"]
    })

    _asyncio_loop = asyncio.get_running_loop()
    _command_queue = asyncio.Queue()
    mqtt_client = setup_mqtt(_asyncio_loop)

    # Start REST server in a daemon thread
    threading.Thread(target=_start_rest_server, daemon=True).start()

    shutdown_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        _asyncio_loop.add_signal_handler(sig, shutdown_event.set)

    await connect_to_px4()
    await configure_telemetry_rates()

    tasks = [asyncio.create_task(_supervised(name, fn)) for name, fn in _TELEMETRY_LOOPS]
    # Publish timers — one per rate-limited topic.  Decoupled from reader loops
    # so the publish rate is controlled here (not by the reader's inbound rate),
    # and object-identity checks can suppress bridge-introduced duplicates.
    for _topic in ("attitude", "velocity", "position", "gps", "battery"):
        _hz = TELEMETRY_RATE_HZ.get(_topic, 20.0)
        tasks.append(asyncio.create_task(
            _supervised(f"pub:{_topic}", lambda t=_topic, h=_hz: _publish_timer(t, h))
        ))
    tasks.append(asyncio.create_task(_staleness_watchdog()))
    tasks.append(asyncio.create_task(_connection_watchdog()))
    tasks.append(asyncio.create_task(_command_loop()))

    log.info("Telemetry → MQTT publishing started")

    await shutdown_event.wait()

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    log.info("Companion bridge shut down")


if __name__ == "__main__":
    asyncio.run(main())
