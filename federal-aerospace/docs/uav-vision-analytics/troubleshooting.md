<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Troubleshooting

## DL Streamer container keeps restarting

- Check logs: `docker logs dlstreamer-pipeline-server`
- Verify the model files exist at `resources/models/yolov8n-visdrone/best_openvino_model/best.xml`
- Confirm `HOST_IP` is set correctly in `.env`

---

## No telemetry overlay on stream (all zeros)

**pymavlink mode:** Confirm `mavlink-router` is running and forwarding MAVLink from PX4:

```bash
docker logs mavlink-router
docker logs px4 | grep -i mavlink
```

**MAVSDK mode:** Confirm the SDK MQTT broker is reachable and publishing telemetry:

```bash
mosquitto_sub -h localhost -p 1884 -t "uav/uav-1/telemetry/#" -v
```

---

## Pipelines not starting in MAVSDK mode

- Confirm `mavsdk_pipeline_manager.py` is running inside the container:
  ```bash
  docker exec dlstreamer-pipeline-server ps aux | grep pipeline
  ```
- Check that the RTSP sources from the SDK are available:
  ```bash
  ffprobe rtsp://localhost:8554/uav-1/nadir
  ```
- Verify the UAV is armed — pipelines only start on ARMED state

---

## NPU inference fails

- Confirm `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so` is set (it is by default in the compose files)
- Check that the NPU device node is available: `ls /dev/accel*`
- Verify driver version: `dmesg | grep -i npu`

---

## GPU pipeline falls back to CPU

- Confirm device group IDs are present: `getent group | grep -E '^(video|render)'`
- The compose files add groups `44`, `109`, `110` for video/render access

---

## QGroundControl — "Network Not Available" warnings

**Symptom:** The following warnings appear in the QGroundControl logs:

```
16.701 Warning: 1 "Network Not Available" - QtLocationPlugin.QGeoTiledMapReplyQGC - (unknown:0)
```

**Cause:** NetworkManager's connectivity check is failing, which causes it to report the network as `limited` or `none` even when the host has a valid local connection.

**Resolution:**

1. Confirm the connectivity state:

    ```bash
    nmcli networking connectivity check   # expected: "limited" or "none"
    ```

2. Disable the NetworkManager connectivity check:

    ```bash
    sudo mkdir -p /etc/NetworkManager/conf.d
    sudo tee /etc/NetworkManager/conf.d/20-connectivity.conf <<'EOF'
    [connectivity]
    enabled=false
    EOF
    sudo systemctl restart NetworkManager
    ```

3. Verify the state is now reported as full:

    ```bash
    nmcli networking connectivity check   # expected: "full"
    ```

---

## PX4 SITL — image pull or runtime issues

**Symptom:** The `px4` service in Docker Compose fails to start or behaves unexpectedly when using the `latest` tag.

**Resolution:** Pin the PX4 SITL image to a known-good digest in `docker-compose-pymavlink.yml`:

```diff
-image: px4io/px4-sitl:latest
+image: px4io/px4-sitl@sha256:01866d912ac22ca6119a996b830cf628a6d47dfb60fdccc41cd9f44b62935a44
```

---

## QGroundControl — outdated version

If QGroundControl itself behaves unexpectedly, ensure you are running the latest stable release.
Installation instructions for Ubuntu: <https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html#ubuntu>

---

## UDP sink pipeline not working

**Symptom:** The UDP sink pipeline fails to send or receive data.

**Resolution:** Replace `127.0.0.1` with `0.0.0.0` in the sink address so it binds to all interfaces:

```diff
-udpsink host=127.0.0.1 port=5600
+udpsink host=0.0.0.0 port=5600
```

**Symptom:** The following warnings appear in the QGroundControl logs:

```
16.701 Warning: 1 "Network Not Available" - QtLocationPlugin.QGeoTiledMapReplyQGC - (unknown:0)
```

**Cause:** NetworkManager's connectivity check is failing, which causes it to report the network as `limited` or `none` even when the host has a valid local connection.

**Resolution:**

1. Confirm the connectivity state:

    ```bash
    nmcli networking connectivity check   # expected: "limited" or "none"
    ```

2. Disable the NetworkManager connectivity check:

    ```bash
    sudo mkdir -p /etc/NetworkManager/conf.d
    sudo tee /etc/NetworkManager/conf.d/20-connectivity.conf <<'EOF'
    [connectivity]
    enabled=false
    EOF
    sudo systemctl restart NetworkManager
    ```

3. Verify the state is now reported as full:

    ```bash
    nmcli networking connectivity check   # expected: "full"
    ```

---

## PX4 SITL — image pull or runtime issues

**Symptom:** The `px4` service in Docker Compose fails to start or behaves unexpectedly when using the `latest` tag.

**Resolution:** Pin the PX4 SITL image to a known-good digest in `docker-compose-pymavlink.yml`:

```diff
-image: px4io/px4-sitl:latest
+image: px4io/px4-sitl@sha256:01866d912ac22ca6119a996b830cf628a6d47dfb60fdccc41cd9f44b62935a44
```

---

## QGroundControl — outdated version

If QGroundControl itself behaves unexpectedly, ensure you are running the latest stable release.
Installation instructions for Ubuntu: <https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html#ubuntu>


---

## UDP sink pipeline not working

**Symptom:** The UDP sink pipeline fails to send or receive data.

**Resolution:** Replace `127.0.0.1` with `0.0.0.0` in the sink address so it binds to all interfaces:

```diff
-udpsink host=127.0.0.1 port=5600
+udpsink host=0.0.0.0 port=5600
```