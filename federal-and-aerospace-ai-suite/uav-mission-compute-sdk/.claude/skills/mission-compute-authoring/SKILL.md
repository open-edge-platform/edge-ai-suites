---
name: mission-compute-authoring
description: Write, run, and debug scripted UAV flight missions against the companion-bridge REST API — waypoint surveys, grid patterns, takeoff/land sequences, orbit patterns. Use when asked to "write a mission", "fly a survey", "add a waypoint script", "make the drone fly a grid/pattern", or when debugging a mission that arms but does not move.
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Mission Authoring

Missions drive the UAV through the **companion-bridge REST API** on port `8080`, not
via MAVSDK directly. The bridge owns the single MAVSDK connection to PX4; a second
client connecting to PX4 in parallel will fight it for control.

## Before writing anything

`sample-apps/mission-simulation/` is referenced in `README.md` and `CLAUDE.md` but
**does not exist in the tree**. If the user asks for a mission, create the directory
and the script — do not assume a template is already there to copy.

Confirm the stack is up and the UAV is connected first:

```bash
curl -s localhost:8080/health
# {"status":"ok","connected":true,"armed":false,"mode":"HOLD"}
```

If `connected` is `false`, the bridge has no PX4 link — every action will return
`"UAV not connected"`. Start the stack (`make up-sim-camera`) before debugging the script.

## REST contract

Source of truth: `infra/bridges/companion/companion_bridge.py:292-330`.

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/health` | — | `{status, connected, armed, mode}` |
| `GET` | `/telemetry` | — | status + home dict (**no live position** — see below) |
| `GET` | `/state` | — | `{success, state}` (back-compat alias, same dict) |
| `POST` | `/action/<action>` | JSON **object** or empty | `{success, error}` |

### REST carries no live position

`GET /telemetry` returns the bridge's `_state` dict verbatim
(`companion_bridge.py:103,319`), and `_state` holds **only**:

```
connected, armed, mode, stale, flight_time_s, timestamp
home_lat, home_lon, home_alt_msl      # added once the first valid GPS fix arrives
```

Live lat/lon/altitude are written to `_latest["position"]` and published to **MQTT only**
(`companion_bridge.py:440`). There is no REST endpoint for current position. A mission that
needs to know where the UAV *is* must subscribe to
`uav/{uav_id}/telemetry/position` on the broker — this is why the documented mission
invocation passes both `REST_API_*` and `MQTT_BROKER_*` env vars.

Position payload keys are suffixed, unlike the bare `home_*` keys:

```json
{"reader_ts_ns": 1758038400123456789, "latitude_deg": 47.3977,
 "longitude_deg": 8.5456, "absolute_altitude_m": 488.2, "relative_altitude_m": 5.1}
```

`POST /action/<action>` returns HTTP **500** with `{"success": false, "error": ...}` on
failure — check `success`, not just the status code. A non-object JSON body (list,
string, number) is rejected with 400.

### Actions

| Action | Body params | Notes |
|---|---|---|
| `arm` | — | Required before `takeoff` |
| `takeoff` | `altitude` (m, default `5.0`) | Sets takeoff altitude then takes off |
| `goto` | `north`, `east` (m, required), `down` (m, default `-5.0`) | NED offset **from home** |
| `land` | — | |
| `return` | — | Return to launch |
| `hold` | — | |
| `disarm` | — | Avoid — see gotchas |
| `kill` | — | Emergency motor cut, not a normal mission step |
| `reboot` | — | |

### `goto` coordinate semantics

`goto` takes **NED metre offsets from the home position**, which the bridge converts to
absolute GPS (`companion_bridge.py:255-269`). Two traps:

- `down` is negated into altitude: `alt = -down`. So `down: -20` means **20 m above** home.
  Passing a positive `down` flies the UAV *below* home altitude.
- Home position must already be known or the action raises `"Home position not yet known"`.
  Home is populated after GPS lock — poll `/telemetry` for `home_lat` before the first `goto`.

Every dispatch blocks up to **15 s** and then returns `"Command timed out"`. `goto` returns as
soon as PX4 *accepts* the target, not on arrival — poll `/telemetry` position to wait for arrival.

## Script skeleton

Place missions in `sample-apps/mission-simulation/`. Read host/port from env so the same
script runs on host and in-container:

Commands go over REST; position feedback comes over MQTT.

```python
import os, time, math, json
import requests
import paho.mqtt.client as mqtt

BASE   = f"http://{os.getenv('REST_API_HOST', 'localhost')}:{os.getenv('REST_API_PORT', '8080')}"
UAV_ID = os.getenv("UAV_ID", "uav-1")

def act(action, **body):
    r = requests.post(f"{BASE}/action/{action}", json=body, timeout=20)
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"{action} failed: {payload.get('error')}")

def status():
    """Status + home only — contains no live position."""
    return requests.get(f"{BASE}/telemetry", timeout=10).json()


class PositionFeed:
    """Live position is MQTT-only. Broker is 1884 from the host, 1883 in-container."""
    def __init__(self):
        self.latest = None
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        c.on_message = lambda _c, _u, msg: setattr(self, "latest", json.loads(msg.payload))
        c.connect(os.getenv("MQTT_BROKER_HOST", "localhost"),
                  int(os.getenv("MQTT_BROKER_PORT", "1884")), 60)
        c.subscribe(f"uav/{UAV_ID}/telemetry/position")
        c.loop_start()
        self._client = c

    def wait(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.latest is not None:
                return self.latest
            time.sleep(0.2)
        raise TimeoutError("no position published — is the bridge connected to PX4?")


def wait_for_home(timeout=60):
    """home_* keys are absent until the first valid GPS fix, then never change."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = status()
        if s.get("home_lat") is not None:
            return s
        time.sleep(1)
    raise TimeoutError("home position never acquired — check GPS fix")


def goto_and_wait(pos: PositionFeed, home, north, east, alt, tol=2.0, timeout=120):
    act("goto", north=north, east=east, down=-alt)   # down is negated into altitude
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = pos.latest
        if p is not None:
            dn = (p["latitude_deg"] - home["home_lat"]) * 111_320.0
            de = ((p["longitude_deg"] - home["home_lon"])
                  * 111_320.0 * math.cos(math.radians(home["home_lat"])))
            if math.hypot(dn - north, de - east) < tol:
                return
        time.sleep(0.5)
    raise TimeoutError(f"never reached ({north}, {east})")
```

The same flat-earth conversion the bridge uses for `goto` is inverted here to measure arrival,
so the two agree. It drifts over long distances — fine for a local survey, not for km-scale legs.

`paho-mqtt` is pinned to 2.1.0 in the app images and `requirements.txt` allows `>=1.6`, which
resolves to 2.x — hence the required `CallbackAPIVersion.VERSION2` argument.

## Running

```bash
make deps   # one-time, from SDK root: creates .venv
cd sample-apps/mission-simulation
MQTT_BROKER_HOST=localhost MQTT_BROKER_PORT=1884 \
REST_API_HOST=localhost REST_API_PORT=8080 \
../../.venv/bin/python mission_1_survey.py
```

## Gotchas

1. **Never call `disarm` after `land`.** PX4 auto-disarms ~20 s after touchdown. An explicit
   disarm races that and can fail or cut motors mid-descent. End missions at `land` and wait.
2. **Cameras only publish while armed.** RTSP streams pause on disarm and the camera-bridge and
   vision-processor tear their pipelines down, rebuilding on re-arm. A mission that disarms
   between legs will drop video each time — keep the UAV armed across the whole run.
3. **After a PX4 restart, bridges need a manual restart.** The MAVSDK connection does not
   re-establish itself cleanly.
4. **`arm` → `takeoff` ordering matters.** `takeoff` on a disarmed UAV fails.
5. Actions are dispatched onto the bridge's asyncio loop from a Flask thread. Concurrent
   commands from two mission scripts interleave unpredictably — run one mission at a time.
