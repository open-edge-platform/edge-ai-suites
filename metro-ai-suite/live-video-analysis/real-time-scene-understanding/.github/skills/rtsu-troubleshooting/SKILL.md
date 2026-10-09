---
name: rtsu-troubleshooting
description: Diagnose Real Time Scene Understanding dashboard, API, RTSP, WebRTC, model, device, storage, and Docker deployment failures.
license: Apache-2.0
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Real Time Scene Understanding Troubleshooting

Use this skill when the dashboard, API, RTSP stream, WebRTC playback, model inference, storage, or Docker deployment is not working as expected.

## First checks

Run these from the repository root:

```bash
docker compose ps
curl --fail http://localhost:${PORT:-9100}/api/health
docker compose logs --tail=200 real-time-scene-understanding
```

If the application is not running, inspect all services:

```bash
docker compose logs --tail=200
```

Do not expose environment files, credentials, tokens, or full exception details in reports.

## Dashboard or API is unreachable

1. Check `docker compose ps` for an exited or restarting application container.
2. Check the application logs.
3. Confirm the published host port is `PORT` and that the dashboard uses `http://<host>:9100` by default.
4. Check `GET /api/health` locally on the host.
5. Validate the Compose configuration without printing interpolated values with `docker compose config --quiet`.

Remember that `DASHBOARD_PORT` is the container port and does not change the published host port in the current Compose file.

## RTSP or WebRTC problems

1. Confirm the RTSP URL is reachable from the machine running the application.
2. Check application logs for stream connection, timeout, or PyAV errors.
3. Confirm the stream host is included in `no_proxy` when a proxy is configured.
4. Confirm MediaMTX and coturn are running.
5. Confirm `HOST_IP`, `WEBRTC_SIGNALING_URL`, and `WEBRTC_SIGNALING_PORT` are suitable for browser access.
6. Check that the WebRTC signaling port and UDP media port are reachable from the browser network.

Treat RTSP URLs and prompts as untrusted input. Do not place camera credentials in logs or diagnostic output.

## Model or device problems

1. Confirm the selected model exists under `ov_models/<device>/<model-name>/`.
2. Confirm the model name and device match `ALERT_VLM_MODEL`, `ALERT_VLM_DEVICE`, `DEEP_ANALYZER_MODEL`, and `DEEP_ANALYZER_DEVICE`.
3. Confirm `/models` is mounted read-only in the application container.
4. For GPU or NPU inference, confirm `/dev/dri`, the configured NPU device, and the required Intel runtime are available.
5. For deep analysis errors about video preprocessing, verify that the selected VLM supports video input.

## SeaweedFS or alert artifact problems

1. Confirm the `seaweedfs` service is healthy.
2. Check the application logs for storage connection or upload failures without printing access keys.
3. Verify the endpoint, bucket, and SSL settings in `.env`.
4. Check retention and segment settings before deleting data.

## Completion criteria

State the observed symptom, the evidence collected, the likely cause, and the next corrective action. Verify the fix with the relevant health check, log result, focused test, or browser/API check.