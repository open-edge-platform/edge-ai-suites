# UAV Vision Analytics — MAVSDK Flow

End-to-end walkthrough: starting the SDK, launching the pipeline manager, running a simple mission, and capturing the video streams.

---

## 1. Start the SDK

```bash
cd federal-aerospace/uav-mission-compute-sdk
```

Follow the setup instructions in the [README](../../uav-mission-compute-sdk/README.md) before proceeding.

---

## 2. Start the pipeline manager

From the `uav-vision-analytics` directory, bring up the DL Streamer container and start the pipeline manager:

```bash
cd edge-ai-suites/federal-aerospace/apps/uav-vision-analytics
make mavsdk-up
make start-rtsp
```

The pipeline manager subscribes to `uav/{id}/telemetry/status` on the SDK's MQTT broker. It automatically starts the inference pipelines when the drone is armed and stops them when disarmed. It also probes each RTSP source with `ffprobe` before starting to confirm the stream is live.

---

## 3. Run a simple mission

> **Note:** Video streams are not available until the drone is armed and actively on a mission.

The following sequence arms the drone, commands a takeoff to 10 m, holds for 20 seconds, then lands:

```bash
curl -X POST http://localhost:8080/action/arm
curl -sf -X POST http://localhost:8080/action/takeoff \
  -H "Content-Type: application/json" \
  -d '{"altitude": 10}'
sleep 20
curl -X POST http://localhost:8080/action/land
```

---

## 4. Capture the video streams

Once the pipeline manager has started the pipeline, record all three streams to disk with `ffmpeg`:

```bash
ffmpeg \
  -rtsp_transport tcp -i rtsp://localhost:8555/nadir \
  -rtsp_transport tcp -i rtsp://localhost:8555/forward \
  -rtsp_transport tcp -i rtsp://localhost:8555/rear \
  -map 0:v -c:v copy nadir.mkv \
  -map 1:v -c:v copy forward.mkv \
  -map 2:v -c:v copy rear.mkv
```
