# Troubleshooting

This page provides troubleshooting steps for common issues. If you encounter a problem not
listed here, check the [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues)
board or file a new ticket.

## General

### Containers Not Starting

**Symptoms**: One or more services fail to start or immediately exit.

**Solution**:

```bash
docker compose logs
```

Check the output for dependency errors (database not ready, missing `.env` variables, port conflicts).

### Port Conflicts

**Symptoms**: A service fails to bind to its port; address already in use.

**Solution**: Update the port variables in `.env` (for example, `UI_HTTPS_PORT`) and restart:

```bash
docker compose down
docker compose up -d
```

### Backend Not Healthy

**Symptoms**: `docker compose ps` shows `vms-adapter-backend` as unhealthy or restarting.

**Solution**:

```bash
docker compose logs vms-adapter-backend
```

Common causes:

- Live Video Captioning or DL Streamer Vision application is not reachable at startup —
  start the Analytics App before VAP.
- `VMS_PLUGIN_DATABASE_URL` is incorrect — verify the PostgreSQL connection string.
- A required environment variable is missing — check for `sys.exit(1)` in the logs.

---

## Camera Discovery

### No Cameras Discovered from Nx Witness

**Symptoms**: Nx Witness cameras are missing after discovery.

**Checks**:

- Verify `NX_HOST`, `NX_USERNAME`, and `NX_PASSWORD` are set correctly in `.env`.
- Confirm the Nx Witness REST API is reachable: `curl -k https://<NX_HOST>:7001/rest/v4/devices`.
- Check that the Nx Witness user has sufficient permissions to list devices.

---

## Live Video Captioning (LVC)

### Analytics Dashboard Shows an Error on Load

**Symptoms**: The Analytics Engine panel shows an error when VAP first starts.

**Cause**: VAP fetches the LVC OpenAPI schema at startup. If LVC is not running, the schema fetch fails.

**Solution**: Start LVC before starting VAP, then restart the VAP backend:

```bash
docker compose restart vms-adapter-backend
```

### Captions Not Appearing in the Dashboard

**Symptoms**: A run is started but no captions appear in the caption overlay.

**Checks**:

- Confirm the RTSP stream is reachable from the LVC `dlstreamer-pipeline-server` container.
- Check LVC logs: `docker compose logs dlstreamer-pipeline-server` (in the LVC stack).
- Verify the SSE stream is connected: open `https://localhost:3443/v1/analytics-apps/live_captioning/results/stream` in a browser.
- If running in a proxy network, add the RTSP stream IP to `no_proxy`.

### WebRTC Video Not Playing

**Symptoms**: The live stream panel shows a black frame or connection failure.

**Checks**:

- Verify `MEDIAMTX_URL` in `.env` points to a reachable MediaMTX instance.
- Confirm `HOST_IP` in the LVC `.env` is reachable from the browser client.
- Check firewall rules allow the WebRTC/WHIP port (`8889`).

### Model Dropdown Is Empty

**Symptoms**: No models appear in the model selector in the dashboard.

**Checks**:

- Ensure LVC's `ov_models/` directory contains at least one model with OpenVINO™ IR files.
- Restart the LVC stack so the service rescans the directory.

---

## DL Streamer Vision (`dls_vision`) based app like Loitering Detection

### VAP Cannot Reach the DL Streamer Pipeline Server

**Symptoms**: Starting a `dls_vision` run fails; backend logs show a connection error to `DLS_VISION_HOST`.

**Checks**:

- Verify `DLS_VISION_HOST` and `DLS_VISION_PORT` in `.env` are correct.
- Confirm the DL Streamer Pipeline Server is running: `curl http://<DLS_VISION_HOST>:8080/pipelines`.
- If `dls_vision` runs on the same host as VAP, use `host.docker.internal` for `DLS_VISION_HOST`.

### No Bounding Boxes Appear in Nx Witness

**Symptoms**: `dls_vision` runs start successfully but detections are not shown in the Nx Witness client.

**Checks**:

- Confirm the MQTT broker is running and reachable at `MQTT_HOST:MQTT_PORT`.
- Verify that the DL Streamer Pipeline Server is publishing inference results to MQTT on the
  expected topic (`/{vms_name}/dls_vision/{camera_id}`).
- Check that the Nx Witness analytics integration was registered successfully: look for
  `register_analytics` in the `vms-adapter-backend` logs.
- Verify integration credentials: if the integration was reused from a previous run, the
  password may not be available. In that case, remove the integration from Nx Witness and
  restart VAP to recreate it.
- Close any camera visualizer window that was already open in the Nx Witness client before the
  pipeline started. With the camera window closed, stop the pipeline and start it again, then
  reopen the camera. A visualizer window opened before strating the analytics does not render overlays correctly. This is Nx Optix limitaion and is being tracked with the Nx team
  in the
  [Network Optix developer forum](https://support.networkoptix.com/hc/en-us/community/posts/42656716334871-Analytics-bounding-box-overlay-not-shown-on-live-camera-view-REST-API-based-integration).

### MQTT Messages Not Received

**Symptoms**: `MqttSubscriber` does not forward detections; no analytics objects appear in Nx.

**Checks**:

- Check the MQTT topic convention: `/{vms_name}/dls_vision/{camera_id}` where `camera_id` is
  the bare Nx device UUID (no `nx:` prefix).
- Verify the `vms_name` in the topic matches the `name` field of the VMS config in `config.yaml`.
- Inspect MQTT traffic using a tool like `mosquitto_sub`:

  ```bash
  mosquitto_sub -h <MQTT_HOST> -t '#' -v
  ```

---

## Database

### PostgreSQL Connection Refused

**Symptoms**: Backend logs show `could not connect to server` or `Connection refused` on startup.

**Checks**:

- Verify the `vms-adapter-postgres` container is healthy: `docker compose ps vms-adapter-postgres`.
- Check `PG_PASSWORD` in `.env` matches the value used to initialize the database.
- If you changed the password after the volume was created, remove the volume and restart:

  ```bash
  docker compose down -v
  docker compose up -d
  ```

---

## Supporting Resources

- [Get Started](./get-started.md)
- [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
