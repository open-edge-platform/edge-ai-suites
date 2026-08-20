<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Capture Camera Frame

Capture a single frame from any UAV camera for debugging/verification.

**Note**: By default, cameras stream via RTSP (not MQTT frames). Use RTSP capture methods below.
To revert to MQTT mode, set `USE_RTSP=false` in docker-compose.yml.

## Usage
Specify which camera to capture:
- Sim mode: `nadir`, `forward`, `rear`
- USB mode: usually `nadir`

## Prerequisite (RTSP mode)
RTSP paths are published only while UAV is armed.
```bash
curl -X POST http://localhost:8080/action/arm
sleep 2
```

## Capture from RTSP (Default Mode)

### Quick capture single frame (requires ffmpeg)
```bash
# Replace <camera> with: nadir (usb mode) or nadir/forward/rear (sim mode)
ffmpeg -i rtsp://localhost:8554/uav-1/<camera> -frames:v 1 /tmp/<camera>_frame.jpg -y

# Verify it's a valid JPEG
file /tmp/<camera>_frame.jpg
```

### Capture all 3 cameras at once
```bash
# Sim mode only
for cam in nadir forward rear; do
  ffmpeg -i rtsp://localhost:8554/uav-1/${cam} -frames:v 1 /tmp/${cam}_frame.jpg -y 2>&1 | grep -q "frame=" && echo "✓ ${cam} captured" || echo "✗ ${cam} failed" &
done
wait
ls -lh /tmp/{nadir,forward,rear}_frame.jpg
```

### Record 5-second video clip
```bash
ffmpeg -i rtsp://localhost:8554/uav-1/nadir -t 5 -c copy /tmp/nadir_clip.mp4
```

### View live stream (requires ffplay)
```bash
ffplay rtsp://localhost:8554/uav-1/nadir
```

If you still get 404, camera publisher is not active yet:
```bash
docker logs camera-bridge --tail 20      # sim mode
docker logs usb-camera-bridge --tail 20  # usb mode
```

## Capture from MQTT (Legacy Mode)

### Quick capture via MQTT (any camera)
```bash
# Replace <camera> with: nadir, forward, or rear
docker exec mqtt-broker mosquitto_sub \
  -t "uav/uav-1/camera/<camera>/frame" \
  -C 1 -W 10 > /tmp/<camera>_frame.jpg

# Verify it's a valid JPEG
file /tmp/<camera>_frame.jpg
identify /tmp/<camera>_frame.jpg 2>/dev/null || python3 -c "
import cv2; img = cv2.imread('/tmp/<camera>_frame.jpg')
print(f'Resolution: {img.shape[1]}x{img.shape[0]}' if img is not None else 'INVALID')
"
```

### Capture all 3 cameras at once
```bash
for cam in nadir forward rear; do
  docker exec mqtt-broker mosquitto_sub \
    -t "uav/uav-1/camera/${cam}/frame" \
    -C 1 -W 10 > /tmp/${cam}_frame.jpg &
done
wait
ls -la /tmp/{nadir,forward,rear}_frame.jpg
```

### Capture processed frame (with detection bounding boxes)
```bash
docker exec mqtt-broker mosquitto_sub \
  -t "uav/uav-1/camera/<camera>/processed" \
  -C 1 -W 10 > /tmp/<camera>_processed.jpg
```

## Verify Camera Angles
Expected views:
- **nadir**: Straight down (ground directly below UAV)
- **forward**: 45° forward-down (sees terrain ahead of UAV)
- **rear**: 45° rear-down (sees terrain behind UAV)

## Check Frame Rate

### RTSP stream stats (requires ffprobe)
```bash
# Get stream info including frame rate
ffprobe -v quiet -print_format json -show_streams rtsp://localhost:8554/uav-1/nadir | jq '.streams[0] | {codec: .codec_name, width, height, fps: .r_frame_rate}'
```

### MQTT frame rate (legacy mode only)
```bash
python3 -c "
import paho.mqtt.client as mqtt
import time, sys

count = [0]
start = [None]

def on_msg(c, u, m):
    if start[0] is None: start[0] = time.time()
    count[0] += 1
    elapsed = time.time() - start[0]
    if elapsed >= 5:
        print(f'{m.topic}: {count[0]/elapsed:.1f} FPS')
        sys.exit(0)

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.on_message = on_msg
c.connect('localhost', 1884)
c.subscribe('uav/uav-1/camera/nadir/frame')
c.loop_forever()
"
```

## RTSP Stream Reference
| RTSP URL | Description |
|----------|-------------|
| `rtsp://localhost:8554/uav-1/nadir` | H264 stream from bottom camera |
| `rtsp://localhost:8554/uav-1/forward` | H264 stream from forward camera |
| `rtsp://localhost:8554/uav-1/rear` | H264 stream from rear camera |

## MQTT Topic Reference (Legacy Mode)
| Topic Pattern | Description |
|---------------|-------------|
| `uav/uav-1/camera/nadir/frame` | Raw JPEG from bottom camera |
| `uav/uav-1/camera/forward/frame` | Raw JPEG from forward camera |
| `uav/uav-1/camera/rear/frame` | Raw JPEG from rear camera |
| `uav/uav-1/camera/<cam>/processed` | JPEG with detection boxes drawn |
| `uav/uav-1/camera/<cam>/detections` | JSON detection metadata |
