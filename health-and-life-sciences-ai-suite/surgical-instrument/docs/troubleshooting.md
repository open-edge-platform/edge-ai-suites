# Troubleshooting

1. `docker compose up` fails with `permission denied` on `/dev/dri/renderD128`
   - The `render` group GID inside the container does not match the host.
     Confirm `getent group render` on the host and re-run `make up` (the
     Makefile auto-detects the render / video GIDs).

2. Basler camera is not detected
   - Run `make list-cameras` to confirm the camera is visible on the host.
   - Ensure the USB device is powered and cabled; the Makefile passes
     `/dev/bus/usb` and a USB cgroup rule so the container can see it.

3. `--presenter gl` fails to start; app falls back to `cv2` or headless
   - The container logs the reason (missing GL libs, `glfwInit()` failure,
     no display server, unsupported GLX/EGL).
   - Ensure `DISPLAY` is set and `xhost +local:root` allows local containers
     to reach the X server.

4. `resolve : lstat /home/.../docker: no such file or directory` during build
   - The compose build context is misconfigured. It must point at the app root
     with `dockerfile: docker/Dockerfile`. Re-check
     [docker/docker-compose.yaml](../../docker/docker-compose.yaml).

5. `make up` says `\: command not found`
   - A stray double backslash (`\\`) is present in the `up` recipe. Ensure
     each continuation is a single `\`.

6. `make up REGISTRY=true` fails to pull
   - Verify the image tag exists in `REGISTRY_URL`. Retry with
     `REGISTRY=false` to build from source while the registry issue is
     resolved.

7. Camera runs but latency is high
   - Enable the low-latency profile:
     `make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER>`.
   - Compare `trigger_to_display_ms` before and after in the CSV output.
   - See the latency reality check in
     [Runtime Configuration](./runtime-configuration.md#latency-reality-check).

8. Model fails to load on GPU
   - Confirm the OpenVINO IR exists at
     `models/yolo11n_polyp/best_openvino_model/best.xml` on the host.
   - Confirm `/dev/dri` is passed through (check `docker exec <container> ls /dev/dri`).

## Local model preparation (`make backend-bootstrap`)

9. `torch.xpu not available` or `RuntimeError: XPU device init failed`
   - Verify host L0 stack: `make check-l0`.
   - Verify `/dev/dri` exists and your user is in the `render` group
     (`id -nG | tr ' ' '\n' | grep -E '^render$'`). Log out and back in after
     `./setup.sh` if you were just added.
   - `torch` must be `>=2.12.1+xpu`; earlier versions stall in Ultralytics'
     loss/assign kernels on Xe/Xe3 iGPUs. Recreate the venv with
     `rm -rf .venv-backend && make backend-venv`.

10. `zeInit failed` at import time
    - The Intel `libze1` / `libze-intel-gpu1` package is missing or a stale
      OpenCL loader is masking Level Zero. Re-run `./setup.sh` and
      `make check-l0`.

11. Dataset auto-detect finds zero paired samples
    - REAL-Colon: confirm sibling `SSS-VVV_frames/` + `SSS-VVV_annotations/`
      directories exist under `datasets/REAL-Colon/raw/` (extracted from the
      `*_frames.tar.gz` / `*_annotations.tar.gz` archives). Frame stems must
      match XML stems.
    - Legacy mask-based drops: image stems must match mask stems (`100.png`
      ↔ `100.png`), and `masks/` must actually contain binary masks (not
      color-coded segmentations).
    - Delete `datasets/*/data.yaml` and rerun `make backend-bootstrap` to
      force re-detection.

12. Reset the trained-model cache
    - The bootstrap step is cache-first. To rebuild from scratch after a
      dataset or config change:
      ```bash
      rm -rf models/yolo11n_polyp/best_openvino_model \
             models/yolo11n_polyp/.trained_ok
      make backend-bootstrap
      ```

13. Missing demo video for `SOURCE=file`
    - Place any endoscopic video at `videos/polyp_test.mp4`, or generate one
      from the REAL-Colon subset with
      `.venv-backend/bin/python scripts/create_endoscopy_video.py`.
