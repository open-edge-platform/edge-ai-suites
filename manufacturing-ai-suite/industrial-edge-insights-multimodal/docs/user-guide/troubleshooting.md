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

``` sh
date
```

Set the correct date/time manually:

``` sh
sudo date -s 'YYYY-MM-DD HH:MM:SS'   # Replace with your actual date and time
```

Set date/time from the internet:

``` sh
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

---

## 5. GPU / NPU Not Accessible Inside a Container

### 5.1 Issue

Any service that mounts `/dev/dri` (GPU) or `/dev/accel` (NPU) fails to use those devices for inference. The failure manifests differently depending on the service:

**dlstreamer-pipeline-server** — pipeline errors with a GStreamer/OpenVINO message in logs:

```bash
{"levelname": "ERROR", ..., "message": "Error on Pipeline ...: gst-library-error-quark: base_inference plugin initialization failed (3): ...
Failed to construct OpenVINOImageInference
    Exception from src/inference/src/cpp/core.cpp:118:
Exception from src/inference/src/dev/plugin.cpp:112:
Check '!m_device_map.empty()' failed at src/plugins/intel_gpu/src/plugin/plugin.cpp:528:
[GPU] Can't get PERFORMANCE_HINT property as no supported devices found or an error happened during devices query.
[GPU] Please check OpenVINO documentation for GPU drivers setup guide.", "module": "gstreamer_pipeline"}
```

**Any other service** — inference either falls back silently to CPU, throws a permission error when opening the device, or reports no GPU/NPU device found. The common indicator across all services is that the device files `/dev/dri/renderD128` and `/dev/accel/accel0` are not readable inside the container.

### 5.2 Reason

Both `/dev/dri/renderD128` and `/dev/accel/accel0` are owned by the `render` group. The `render` group GID is **typically 992 on Ubuntu 24.04**, but the actual GID varies per system depending on the order in which system groups were created. If another group (e.g. `systemd-resolve`) was allocated before the GPU driver created the `render` group, the GID will be shifted — commonly to **993**.

The `group_add` section in `docker-compose.yml` lists the expected GIDs, but if the host's `render` GID is not in that list, the container process cannot read the device files.

### 5.3 Diagnosis

**Step 1 — Find the actual render group GID on the host:**

```bash
getent group render
```

Example output:

```
render:x:993:user
```

The third field (`993`) is the GID. If it differs from the values in `group_add`, that is the problem.

**Step 2 — Confirm via device file ownership:**

```bash
stat /dev/dri/renderD128
stat /dev/accel/accel0
```

Look for the `Gid:` line in the output:

```
Access: (0660/crw-rw----)  Uid: (    0/    root)   Gid: (  993/  render)
```

**Step 3 — Verify inside the container:**

For Docker Compose:

```bash
docker exec <container-name> bash -c "test -r /dev/dri/renderD128 && echo 'GPU: accessible' || echo 'GPU: NOT accessible'"
docker exec <container-name> bash -c "test -r /dev/accel/accel0 && echo 'NPU: accessible' || echo 'NPU: NOT accessible'"
```

> **Note:** For Helm deployment, use `kubectl exec` instead:
> ```bash
> kubectl exec -n <namespace> <pod-name> -- bash -c "test -r /dev/dri/renderD128 && echo 'GPU: accessible' || echo 'GPU: NOT accessible'"
> kubectl exec -n <namespace> <pod-name> -- bash -c "test -r /dev/accel/accel0 && echo 'NPU: accessible' || echo 'NPU: NOT accessible'"
> ```
> To find the pod name: `kubectl get pods -n <namespace>`

### 5.4 Solution

**Step 1 — Add the correct render GID to the service configuration:**

First find the actual render GID on the host (from Step 1 of Diagnosis above), then update the relevant configuration depending on how the service is deployed.

**For Docker Compose deployments** — open `docker-compose.yml` and locate the `group_add` section for the affected service:

```yaml
group_add:
  # render group ID for ubuntu 20.04 host OS
  - "109"
  # render group ID for ubuntu 22.04 host OS
  - "110"
  # render group ID for ubuntu 24.04 host OS
  - "992"
  # render group ID on this host (verify with: getent group render)
  - "993"
```

**For Helm deployments** — open the relevant Helm template (e.g. `helm/templates/dlstreamer-pipeline-server.yaml`) and locate the `supplementalGroups` field under `securityContext`. Add the GID returned by `getent group render`:

```yaml
securityContext:
  supplementalGroups: [109, 110, 992, 993]  # render group IDs for ubuntu 20.04, 22.04, 24.04 host OS
```

Replace `993` with the actual GID on your system if it differs.

**Step 2 — Restart the stack:**

For Docker Compose:

```bash
make down
make up
```

> **Note:** For Helm deployment, follow the uninstall and install steps in the [Getting Started](./get-started/deploy-with-helm.md) guide to redeploy the stack after editing the Helm template.

**Step 3 — Verify the fix:**

Check that the device files are now readable inside the container:

```bash
docker exec <container-name> bash -c "
  test -r /dev/dri/renderD128 && echo 'GPU: accessible' || echo 'GPU: NOT accessible'
  test -r /dev/accel/accel0   && echo 'NPU: accessible' || echo 'NPU: NOT accessible'
"
```

Expected output:

```bash
GPU: accessible
NPU: accessible
```
