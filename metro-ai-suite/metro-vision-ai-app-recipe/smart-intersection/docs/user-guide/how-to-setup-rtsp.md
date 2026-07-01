# RTSP Stream Setup

Steps to serve the intersection `.ts` video files over RTSP using mediamtx and ffmpeg.

## Prerequisites

- `<rtsp-server-IP>`: Machine IP that runs mediamtx (Check with`hostname -I`)
- Port `8554` must not be blocked by firewall

## 1. Download mediamtx

```bash
wget https://github.com/bluenviron/mediamtx/releases/download/v1.9.0/mediamtx_v1.9.0_linux_amd64.tar.gz
tar xzf mediamtx_v1.9.0_linux_amd64.tar.gz
```

This extracts `mediamtx` binary and `mediamtx.yml` config.

## 2. Start mediamtx RTSP server

```bash
nohup ./mediamtx &
```

By default it listens on `:8554` (all interfaces).

## 3. Install ffmpeg

```bash
sudo apt-get install -y ffmpeg
```

## 4. Download the video file

```bash
curl -k -L -o 1122north_h264.ts \
  "https://github.com/open-edge-platform/edge-ai-resources/raw/refs/heads/main/videos/1122north_h264.ts"
```

Other available videos:

- `1122east_h264.ts`
- `1122west_h264.ts`
- `1122south_h264.ts`

## 5. Publish the stream

```bash
ffmpeg -stream_loop -1 -re -i 1122north_h264.ts -c copy -f rtsp rtsp://localhost:8554/north
```

To run in background:

```bash
nohup ffmpeg -stream_loop -1 -re -i 1122north_h264.ts -c copy -f rtsp rtsp://localhost:8554/north > /tmp/ffmpeg_rtsp.log 2>&1 &
```

## 6. Verify the stream

```bash
ffprobe rtsp://localhost:8554/north
```

Expected output: H.264 High profile, 1280x720, 30fps.

## Access

- Local: `rtsp://localhost:8554/north`
- Remote: `rtsp://<rtsp-server-IP>:8554/north`

## Multiple streams

To serve all four cameras:

```bash
ffmpeg -stream_loop -1 -re -i 1122north_h264.ts -c copy -f rtsp rtsp://localhost:8554/north &
ffmpeg -stream_loop -1 -re -i 1122south_h264.ts -c copy -f rtsp rtsp://localhost:8554/south &
ffmpeg -stream_loop -1 -re -i 1122east_h264.ts  -c copy -f rtsp rtsp://localhost:8554/east &
ffmpeg -stream_loop -1 -re -i 1122west_h264.ts  -c copy -f rtsp rtsp://localhost:8554/west &
```

## 7. Configure the DL Streamer pipeline

Edit `smart-intersection/src/dlstreamer-pipeline-server/config.json` to switch a camera from the local video file to the RTSP source.

Replace the `multifilesrc` source element in the pipeline string:

**Before (local file):**

```
multifilesrc loop=true location=/home/pipeline-server/videos/1122north_h264.ts
```

**After (RTSP source):**

```
urisourcebin uri=rtsp://<rtsp-server-IP>:8554/north
```

Replace `<rtsp-server-IP>` with the IP of the machine running mediamtx.

To use all four RTSP streams, update each camera pipeline accordingly:

| Pipeline            | RTSP URI                          |
| ------------------- | --------------------------------- |
| `intersection-cam1` | `rtsp://<mediamtx-ip>:8554/north` |
| `intersection-cam2` | `rtsp://<mediamtx-ip>:8554/east`  |
| `intersection-cam3` | `rtsp://<mediamtx-ip>:8554/south` |
| `intersection-cam4` | `rtsp://<mediamtx-ip>:8554/west`  |

## 8. Restart the pipeline server

After editing `config.json`, recreate the container to pick up the changes:

```bash
cd smart-intersection/src
docker compose up -d --force-recreate dlstreamer-pipeline-server
```

Verify the RTSP source is active in the logs:

```bash
docker logs metro-vision-ai-app-recipe-dlstreamer-pipeline-server-1 2>&1 | grep "element"
```

You should see `'element': 'urisourcebin'` for the cameras configured with RTSP, confirming the stream is being consumed from the remote source.
