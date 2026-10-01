# Troubleshooting

This article contains troubleshooting steps for known issues. If you encounter any problems
with the application not addressed here, check the [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues)
board. Feel free to file new tickets there (after learning about the guidelines for [Contributing](https://github.com/open-edge-platform/edge-ai-suites/blob/main/CONTRIBUTING.md)).

## 1. Seeing "No Data" in Grafana

### 1.1 Issue

Grafana panels show **"No Data"** even though the container/stack is
running.

### 1.2 Reason

The **system date/time is incorrect** on the device. If the system time
is wrong, data timestamps fall outside Grafana's query window.

### 1.3 Solution

Check the date/time using the command below:

```bash
date
```

Set the correct date/time manually:

```bash
sudo date -s 'YYYY-MM-DD HH:MM:SS'   # Replace with your actual date and time
```

Set date/time from the internet:

```bash
sudo date -s "$(wget --method=HEAD -qSO- --max-redirect=0 google.com 2>&1 | sed -n 's/^ *Date: *//p')"
```

---

## 2. Influx -- Data Being Deleted Beyond Retention Policy (RP)

### 2.1 Issue

- Data appears to be deleted beyond the configured retention policy
  (RP).
- InfluxDB 1.x deletes old data based on the retention policy duration
  and shard group duration.

### 2.2 Reason

- Data is grouped into **shards**.
- Shards are deleted only when **all data inside them** is older than
  the RP.
- For RPs **≤ 2 days**, shard group duration = **1 hour**.
- InfluxDB always expires data at **RP + shard duration**.

Example:

For a **1-hour RP**: - Data written at **00:00** goes into the shard
covering **00:00--01:00**. - The shard closes at **01:00**. - InfluxDB
deletes the shard only when everything inside it is past the RP → at
**02:00**.

So the effective expiration time is **1 hour RP + 1 hour shard duration
= 2 hours**.

| Retention Policy | Shard Duration |Actual Expiry |
|---|---|---|
| 1 hour | 1 hour | 2 hours |
| 2 days | 1 hour | 2 days + 1 hr |
| 30 days | 24 hours | 30 days + 24 hr |

### 2.3 Solution

- Understand that this is **normal and expected behavior** in InfluxDB 1.x.
- A 1-hour RP will **always** result in \~2 hours before deletion.
- No configuration can force deletion exactly at the RP limit.

---

## 3. Time Series Analytics Microservice (Docker) -- Takes Time to Start or Shows Python Packages Installing

### 3.1 Issue

The Time Series Analytics Microservice takes time to start or displays
messages about Python packages being installed.

### 3.2 Reason

UDF packages require several dependent packages to be installed during
runtime, as specified under `udfs/requirements.txt`. Once these
dependencies are installed, the **Time Series Analytics** microservice
initializes and starts inferencing.

### 3.3 Solution

No action required --- wait for the **time-series-analytics**
microservice to complete downloading the dependent packages and
initialize Kapacitor to start inference.

## 4. `docker exec` issues on the EMT operating system with Alpine-based images

### 4.1 Issue

Running `docker exec` on the `ia-mqtt-broker` container on the EMT operating system (EMT OS) results in the following error:
`OCI runtime exec failed: exec failed: unable to start container process: error writing config to pipe: write init-p: broken pipe: unknown`

### 4.2 Reason

On EMT OS, containers built on Alpine base images can trigger an OCI exec pipe error, causing `docker exec` to fail even though the container itself continues to run correctly.

### 4.3 Solution

As a workaround, run the following steps to be able to successfully exec and execute the command.
As the container is functioning as expected, please ignore any `unhealthy` status showing up against this
container in `docker ps`.

```bash
PID=$(docker inspect --format '.State.Pid' ia-mqtt-broker)
sudo nsenter -t "$PID" -m -u -i -n -p mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
```

## 5. coturn/mediamtx -- Periodic `CreatePermission`/`CHANNEL_BIND` `error 400: Bad Request` log messages

### 5.1 Issue

The `coturn` container logs repeatedly show entries like:

```text
session 008000000000000292: realm <turn.local> user <mediamtx>: incoming packet CHANNEL_BIND processed, success
session 008000000000000292: realm <turn.local> user <mediamtx>: incoming packet message processed, error 400: Bad Request
```

and the `mediamtx` container logs repeatedly show:

```text
turnc ERROR: Fail to refresh permissions: CreatePermission error response (error 400: )
```

These recur every couple of minutes, even while WebRTC/TURN video streaming continues to work correctly.

### 5.2 Reason

This is a long-standing, unresolved upstream interoperability issue between the `pion/turn` TURN client
library (used internally by mediamtx's WebRTC/TURN client, `turnc`) and coturn.

mediamtx's TURN client periodically resends a `CreatePermission`/`CHANNEL_BIND` request to refresh the
permission on its TURN allocation, and coturn intermittently answers with `error 400` for that refresh. In
practice, WebRTC peer connections in this sample app establish directly over `host` ICE candidates (the
mediamtx and browser/client peers reach each other directly on the same network), so the TURN relay
allocation being refreshed is a fallback path that is not actually carrying the media -- mediamtx keeps it
alive only in case direct connectivity is ever lost. A failed refresh on that unused fallback allocation does
not interrupt the active (direct) media path.

This has only been observed when `HOST_IP` is set to a real, host-reachable, non-loopback IP address (the
setting needed for remote UI/WebRTC access); it does not occur when `HOST_IP` is left at the default
`localhost`. This is because `HOST_IP` is also the address that coturn advertises to WebRTC clients for
TURN candidates (`MTX_WEBRTCICESERVERS2_0_URL=turn:${HOST_IP}:${COTURN_UDP_PORT}`). With `HOST_IP=localhost`,
that TURN candidate is only reachable from the same host, so browsers/clients running on that same host
already connect over `host`/loopback ICE candidates before ICE ever needs to gather and hold a TURN relay
candidate -- mediamtx's TURN client has no live allocation to refresh, so the refresh cycle (and its
intermittent `error 400`) never triggers. Once `HOST_IP` is a real network-reachable address, remote clients
and multi-host access patterns cause mediamtx to gather and keep a TURN relay allocation alive as a fallback
candidate, which is what exposes the periodic refresh failures described above.

### 5.3 Solution

No action required -- these messages are benign log noise from an unresolved upstream library issue and do
not affect WebRTC/TURN functionality. Video streaming, permission grants for the active path, and the overall
sample app continue to work as expected. If you want to confirm functionality is unaffected, check the
mediamtx logs for a line such as `peer connection established, local candidate: host/..., remote candidate:
host/...`, which indicates media flowed over a direct connection rather than through the TURN relay.

