<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Switch Camera Mode

Switch the stack between simulated 3-camera mode and real USB camera mode.

## Usage
- `/switch-camera-mode sim` for Gazebo cameras (`nadir,forward,rear`)
- `/switch-camera-mode usb` for one USB camera (`nadir`)

## Implementation

### Sim mode
```bash
#!/bin/bash
set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

echo "Switching to sim camera mode..."

if [ ! -f .env ]; then
  make init
fi

# VISION_CAMERA_IDS is set automatically by make up-sim-camera
make down || true
make up-sim-camera

echo "Done. Sim mode active (nadir, forward, rear)."
```

### USB mode
```bash
#!/bin/bash
set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

echo "Switching to USB camera mode..."

if [ ! -f .env ]; then
  make init
fi

# Discover USB video devices (informational)
v4l2-ctl --list-devices || true

# VISION_CAMERA_IDS is set automatically by make up-usb-camera
# Ensure USB defaults exist if missing
grep -q '^USB_VIDEO_DEVICE=' .env || echo 'USB_VIDEO_DEVICE=/dev/video32' >> .env
grep -q '^USB_CAMERA_ID=' .env || echo 'USB_CAMERA_ID=nadir' >> .env
grep -q '^USB_CAPTURE_FORMAT=' .env || echo 'USB_CAPTURE_FORMAT=mjpeg' >> .env

make down || true
make up-usb-camera

echo "Done. USB mode active (nadir)."
```

## Verification
```bash
docker compose ps
docker logs vision-processor-multicam 2>&1 | grep "Cameras:" | tail -1
```
Expected:
- sim: `Cameras: ['nadir', 'forward', 'rear']`
- usb: `Cameras: ['nadir']`

## Common Issues
- RTSP 404 after switching: arm UAV first
  ```bash
  curl -X POST http://localhost:8080/action/arm
  ```
- USB stream missing: verify `.env` `USB_VIDEO_DEVICE` is correct from `v4l2-ctl --list-devices`
