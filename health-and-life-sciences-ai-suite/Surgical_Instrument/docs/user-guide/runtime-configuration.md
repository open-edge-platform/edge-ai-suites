# Runtime Configuration

Everything reconfigurable at runtime lives in the **Settings** modal,
opened via the `Settings` button in the top action bar, next to Start/Stop.

**First launch.** The app opens with a one-time **research-use disclaimer**
that must be acknowledged before the main UI is interactive. The ack is
stored in `localStorage` under `surgical_disclaimer_ack_v1` and does not
survive a browser-profile wipe.

## Input Source tab

Pick where frames come from without editing config files or restarting
compose. Three source kinds are supported; kinds with no detected devices
are visible but disabled so it is clear what the app supports.

| Kind | Argument | Populated by |
|---|---|---|
| **Video file** | basename under `./videos/` | `GET /api/videos` — lists everything with `.mp4 .mkv .avi .mov .ts` |
| **USB / v4l2 camera** | `/dev/videoN` | `GET /api/devices/cameras` — reads `/sys/class/video4linux` |
| **Basler camera** | serial number | `GET /api/devices/cameras` — pypylon enumeration (ships in Slice E) |

- **Upload** a new video with the "Choose file..." button (max 500 MB, extension whitelist enforced server-side). New uploads land in the same `./videos/` volume and appear in the dropdown immediately.
- **Apply** persists the selection client-side. It takes effect on the **next** Start — the pipeline rejects source changes mid-stream. If a pipeline is running, the modal shows a banner and blocks changes until you Stop.
- **Cameras** are compose-time devices. Hot-plugging after `make up` requires
  `make run` (or the equivalent `docker compose up -d`) so the container can
  see the new node — the UI picker only surfaces what is already mounted.

## Devices tab

Single-row table (`Workload · Model · Device`) with a dropdown for the
polyp-detection accelerator: `CPU`, `GPU` (Intel Arc iGPU — recommended),
`NPU` (Intel AI Boost). Save applies the change on the next Start; Reset
session clears the last inference session's aggregates without stopping the
backend process.

## Backend contract (for scripting / smoke tests)

The UI is a thin wrapper over these endpoints, so any of them can be driven
from `curl` for automation.

| Endpoint | Purpose |
|---|---|
| `GET /api/videos` | List `{name, size_bytes, mtime}` under `VIDEOS_DIR` (default `/videos`) |
| `POST /api/videos` | Multipart upload (`file` field). `415` for wrong ext, `409` for duplicate, `413` for oversize |
| `GET /api/devices/cameras` | `{v4l2:[…], basler:[…], basler_note?}` |
| `GET /api/config` | Reflects live source: `{video_file, default_video, source:{kind,arg}, devices:{detect}}` |
| `POST /api/start` | Optional body: `{device?, source?:{kind,arg}}` — persisted to `ServerState` for subsequent Starts |
| `POST /api/stop` · `POST /api/reset` | Lifecycle |
| `POST /api/device` | Set active accelerator for the polyp-detection workload |

## Pre-flight: `make doctor`

Read-only diagnostic that checks the host before you run `make up`. Reports
each item as `[ OK ]`, `[WARN]`, or `[FAIL]`; exits non-zero only on genuine
fatals (missing Docker, no video assets, port collision with a foreign
process). Own-stack aware — if `surgical-ui` is already running on
`UI_HOST_PORT`, that is reported as OK, not as a conflict.

Sections: host prerequisites · accelerator visibility · cameras · assets ·
port availability · compose config. Sample output:

```
[doctor] --- accelerator visibility ---
  [ OK ] /dev/dri present (renderD* count: 1)
  [ OK ] /dev/accel/accel0 present (NPU visible)
[doctor] --- assets ---
  [ OK ] cached IR : models/yolo11n_polyp/best_openvino_model (5.4M)
  [ OK ] 2 demo video(s) under ./videos/
[doctor] --- port availability ---
  [ OK ] port 8080 free
[doctor] all critical checks passed — `make up` should succeed.
```