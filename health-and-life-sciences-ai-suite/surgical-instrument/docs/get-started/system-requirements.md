# System Requirements

| Requirement | Notes |
|---|---|
| Linux with Docker Engine ≥ 24 and `docker compose` v2 | Rootless Docker works if `/dev/dri` is accessible. |
| Intel Arc iGPU (Meteor Lake / Lunar Lake / Arrow Lake) or discrete Arc GPU | Container inherits the host driver via `/dev/dri` passthrough. |
| Intel client GPU stack (Level Zero + OpenCL + iHD) | `libze1`, `libze-intel-gpu1`, `intel-igc-core-2`, `libigdgmm12`, `intel-opencl-icd`, `intel-media-va-driver-non-free`. Installed by `./setup.sh`; verified by `make check-l0`. |
| Host groups `render` and `video` exist | The Makefile auto-detects the GIDs. `./setup.sh` adds the current user if missing. |
| X11 display server reachable from the container | Required by the OpenGL vsync presenter and the `cv2` fallback. |
| USB access for Basler camera (optional) | The Makefile passes `/dev/bus/usb` and the USB device cgroup rule. |
| `pypylon` compatible Basler camera (optional) | Only required for `SOURCE=camera`. |
| OpenVINO IR model artifacts | Bind-mount under `MODELS_DIR` (default `../models`). Produced by [Model Preparation](./model-preparation.md) if not pulled from the registry. |
| Demo video (optional) | Bind-mount under `VIDEOS_DIR` (default `../videos`). |

## Optional (local model preparation only)

The following are needed only when you build the OpenVINO IR locally via
`make backend-bootstrap` (see [Model Preparation](./model-preparation.md)).

| Requirement | Notes |
|---|---|
| Python 3.10–3.12 with `python3-venv` | Host-side training venv (`.venv-backend`). Installed by `./setup.sh`. |
| REAL-Colon dataset subset (~74 GB) | Downloaded via `./download_realcolon_subset.sh` from figshare article `22202866`. Full 60-study, ~880 GB corpus available via `datasets/REAL-Colon/helper/download_dataset.sh`. |
| Disk space | ~80 GB free for the REAL-Colon subset + derived labels + trained artifacts. Plan more for the full corpus. |
| `torch>=2.12.1+xpu` compatible driver | Required so Ultralytics' loss/assign kernels run on the Xe/Xe3 iGPU. Earlier torch-xpu versions stall. |

Verify iGPU visibility on the host before starting:

```bash
ls -l /dev/dri/renderD*
getent group render
getent group video
```

Verify the display server is reachable from your shell:

```bash
echo $DISPLAY
xhost +local:root  # only needed for X11-restricted environments
```

## Model and video layout

Expected host layout (bind-mounted read-only for models, read/write for videos):

```text
models/yolo11n_polyp/best_openvino_model/best.xml
models/yolo11n_polyp/best_openvino_model/best.bin
videos/polyp_test.mp4
```

Override the mounted host paths when necessary:

```bash
make up MODELS_DIR=/path/to/models VIDEOS_DIR=/path/to/videos SERIAL=<SERIAL_NUMBER>
```

## Corporate proxy setup

If you are behind a corporate proxy, export the standard proxy variables in the
shell you run `make up` from. They are forwarded to `docker build` (as build
args) and to the running container (as environment variables).

```bash
export HTTP_PROXY=http://proxy.your-corp.com:912
export HTTPS_PROXY=http://proxy.your-corp.com:912
export NO_PROXY=localhost,127.0.0.1,.your-corp.com
```

Notes:

- Docker daemon also needs a proxy configuration to pull the base image.
  If `docker pull ubuntu:24.04` works, you are fine. Otherwise configure
  `~/.docker/config.json` or `/etc/systemd/system/docker.service.d/http-proxy.conf`
  per your IT policy.
