# Multiple Scenescape Deployment

Smart NVR with Scenescape running on separate machines: Smart Intersection (SI) on
System 1, NVR stack on System 2. For single-node deployment, see
[Integrate Scenescape with Smart NVR](./scenescape-integration.md).

## Overview

Smart NVR maintains a persistent, independent MQTT connection to each SI node.
Events are tagged with the broker `id` to route them to the correct Frigate camera.

- **RTSP and MQTT are decoupled.** `brokers.yaml` holds only MQTT broker IPs. RTSP
  streams are configured separately via prompts or env vars at startup.
- **Camera naming.** Frigate cameras must be named `{broker_id}-camera{n}`
  (e.g. `si1-camera1`). The broker `id` must match this prefix exactly.
- **Brokers persist.** On startup, the broker manager reads `brokers.yaml`, seeds
  Redis, and starts one connection per enabled broker. The API persists changes back
  to this file.

## Prerequisites

- VSS must be running and reachable from System 2.
- See [system requirements](./get-started/system-requirements.md) for hardware prerequisites.

## Configuration

### brokers.yaml

Edit `resources/broker-config/brokers.yaml` before starting, or manage brokers at
runtime via the API.

```yaml
# resources/broker-config/brokers.yaml
brokers:
  - id: si1                          # Must match Frigate camera prefix: si1-camera*
    name: Smart Intersection 1
    host: <si1_ip>                    # MQTT broker IP — NOT the RTSP source
    port: 1883
    topic: scenescape/data/camera/#
    type: scenescape
    throttle_interval: 2.0
    enabled: true

  - id: si2
    name: Smart Intersection 2
    host: <si2_ip>
    port: 1883
    topic: scenescape/data/camera/#
    type: scenescape
    throttle_interval: 2.0
    enabled: true
```

> TLS is enabled by default. Broker connections do not use username or password authentication.

### Broker fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `id` | ✅ | — | Unique identifier. Must match the Frigate camera name prefix (e.g. `si1` → `si1-camera*`). |
| `name` | ✅ | — | Human-readable label. |
| `host` | ✅ | — | MQTT broker IP address. |
| `topic` | ✅ | — | MQTT topic to subscribe to. |
| `port` | — | `1883` | MQTT broker port. |
| `type` | — | `scenescape` | Event type. Always `scenescape` for SI nodes. |
| `use_tls` | — | `true` | Enable TLS. Set to `false` for plain MQTT brokers. |
| `throttle_interval` | — | `2.0` | Minimum seconds between processed events. |
| `enabled` | — | `true` | Set to `false` to disable on startup without removing. |

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NVR_SCENESCAPE` | ✅ | — | Must be `true` to enable Scenescape mode. |
| `VSS_IP` | ✅ | — | VSS service IP. The single nginx proxy serves both summary and search. |
| `VSS_PORT` | — | `12345` | VSS service port. |
| `MQTT_USER` | — | auto-generated | Local Mosquitto username (Frigate ↔ NVR). |
| `MQTT_PASSWORD` | — | auto-generated | Local Mosquitto password. |
| `SI_RTSP_HOST` | — | prompt | RTSP IP for si1. Prompts interactively (`start-nvr`) or auto-detected (`start`) if unset. |
| `SI{N}_RTSP_HOST` | — | prompt | RTSP IP for siN (N ≥ 2). Prompts interactively if unset. |
| `RTSP_STREAM_PORT` | — | `8554` | RTSP port for all SI streams. |
| `SCENESCAPE_MQTT_BROKER` | — | — | Legacy: seeds si1 MQTT broker into Redis on startup. Prefer `brokers.yaml` or the API. |
| `BROKERS_CONFIG_PATH` | — | `resources/broker-config/brokers.yaml` | Path to broker config file. |
| `MAX_CONCURRENT_EVENTS` | — | `50` | Maximum simultaneous in-flight event tasks. |
| `BROKER_RECONNECT_DELAY` | — | `5.0` | Seconds before reconnecting after a broker disconnect. |

## Deployment

### System 1 — SI node(s)

```bash
export NVR_SCENESCAPE=true
# export SI_RTSP_HOST=<external_rtsp_ip>  # optional: use an external RTSP source
# export RTSP_STREAM_PORT=<port>              # optional, default 8554
source setup.sh start-si
```

Downloads demo videos and starts a local MediaMTX RTSP streamer by default.
Setting `SI_RTSP_HOST` to a remote IP skips the local streamer.

On exit, the script prints System 1's IP and MQTT port — use these when adding the
broker on System 2.

### System 2 — NVR node

```bash
export NVR_SCENESCAPE=true
export VSS_IP=<ip>
export VSS_PORT=<port>              # optional, default 12345

# Optional: pre-set RTSP IP to skip interactive prompts
# export SI_RTSP_HOST=<si1_ip>

source setup.sh start-nvr
```

`start-nvr` prompts for the number of SI nodes and their RTSP IPs. Add MQTT brokers
after startup via `POST /brokers/`, or pre-populate `brokers.yaml` before running
`start-nvr` to load them automatically.

> **Note:** If `brokers.yaml` is absent and `SCENESCAPE_MQTT_BROKER` is not set,
> no MQTT connections are established on startup. Add brokers via `POST /brokers/`
> after the stack is running.

## Stop

```bash
source setup.sh stop-nvr   # System 2
source setup.sh stop-si    # System 1
```

If a local RTSP streamer is running on System 1, `stop-si` prompts:

```
Local RTSP streamer is running. Stop it too? [y/N]
```

Respond `y` to stop it, or `n` to leave it running (`source setup.sh stop-streamer`
stops it independently).

## RTSP Streamer

To manage the MediaMTX RTSP streamer on System 1 independently of SI services.
`start-streamer` downloads demo videos if not already present, then starts the streamer.

```bash
source setup.sh start-streamer
source setup.sh stop-streamer
```

## Managing brokers at runtime

The `/brokers/` API modifies live broker connections without restarting the stack.
Changes persist to `brokers.yaml` automatically.

```bash
BASE=http://localhost:8000

# List brokers
curl $BASE/brokers/

# Add a broker (starts MQTT connection immediately)
curl -X POST $BASE/brokers/ \
  -H "Content-Type: application/json" \
  -d '{
    "id": "si3",
    "name": "Smart Intersection 3",
    "host": "<si3_ip>",
    "topic": "scenescape/data/camera/#"
  }'

# Update a broker (restarts its MQTT connection)
curl -X PUT $BASE/brokers/si3 \
  -H "Content-Type: application/json" \
  -d '{
    "id": "si3",
    "name": "SI 3 updated",
    "host": "<si3_ip_updated>",
    "topic": "scenescape/data/camera/#",
    "enabled": true
  }'

# Remove a broker (stops its MQTT connection)
curl -X DELETE $BASE/brokers/si3
```

> Adding a broker via the API updates MQTT routing only. To record video from a new
> SI node, re-run `setup.sh start-nvr` to regenerate Frigate camera blocks.

## Frigate camera configuration

`setup.sh` generates `resources/frigate-config/config.yml` at startup. It prompts
for the number of SI nodes, then appends 4 camera blocks per node
(`{broker_id}-camera1` through `camera4`):

| SI node | RTSP IP source |
|---------|----------------|
| si1 | `SI_RTSP_HOST` if set; else interactive prompt (`start-nvr`) or auto-detected (`start`) |
| si2..siN | `SI{N}_RTSP_HOST` → interactive prompt |

All cameras use `RTSP_STREAM_PORT` (default `8554`).

## Verify integration

```bash
# Confirm all broker tasks started
docker logs nvr-event-router | grep "subscribed to"
# Expected:
#   [si1] subscribed to scenescape/data/camera/# at <si1_ip>:1883
#   [si2] subscribed to scenescape/data/camera/# at <si2_ip>:1883

# Monitor live events
docker logs nvr-event-router -f | grep "Scenescape event"

# Check reconnection attempts
docker logs nvr-event-router | grep "reconnecting"
```

## Troubleshooting

**Broker connects but no events appear**

- Verify the broker `id` matches the Frigate camera prefix (e.g. `id: si2` → `si2-camera1..4`).
- Confirm SI is publishing to `scenescape/data/camera/#`.

**`[siN] connection error: [Errno 111] Connect call failed`**

MQTT port unreachable. The broker manager retries automatically. Check connectivity:

```bash
nc -zv <siN_host> 1883
```

**Frigate cameras show no recordings**

RTSP IPs are written into `config.yml` at startup. If they changed, re-run
`setup.sh start-nvr` to regenerate the config.

**UI shows no Scenescape source**

```bash
docker exec nvr-event-router-ui env | grep NVR_SCENESCAPE
```

Confirm `NVR_SCENESCAPE=true` is exported in the shell running `setup.sh start-nvr`.

For general issues, see the [Troubleshooting Guide](./troubleshooting.md).
