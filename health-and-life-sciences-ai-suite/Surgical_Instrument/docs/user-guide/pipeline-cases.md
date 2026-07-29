# Pipeline Cases — configurable via `make up`

The DL Streamer pipeline in this application is fully configurable at
`make up` time via a small set of environment variables. Three canonical
cases exercise the surface: tuned live inference (the demo default),
minimum viable camera-to-window pipeline, and the same tuned pipeline
with the `gvawatermark` overlay toggleable.

All three cases run through the same code path
([pipeline/pipeline_string.py](../../pipeline/pipeline_string.py)) and the
same control-plane launcher ([pipeline/launcher.py](../../pipeline/launcher.py)).
No standalone scripts, no side channels — everything is `make up VAR=…`.

---

## Configuration knobs

Set any of these on the `make up` command line. Every knob is optional and
has a documented default.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SOURCE_KIND` | `file` | `file` = recorded MP4, `basler` = live Basler camera |
| `SOURCE_ARG` | `/videos/polyp_test.mp4` | file path (in-container) or Basler serial |
| `DETECT` | `1` | `1` inserts `gvadetect` (+ optional watermark) into the chain; `0` skips it |
| `WATERMARK` | `1` | when `DETECT=1`, `1` keeps `gvawatermark`; `0` drops it (raw video, no overlay) |
| `MINIMAL` | `0` | `1` collapses the pipeline to `source ! rawvideoparse ! videoconvert ! sink` (nothing else) |
| `SCHEDULING_POLICY` | *(unset)* | if set, appended as `scheduling-policy=<val>` on `gvadetect` (e.g. `latency`) |
| `BATCH_SIZE` | *(unset)* | if set, appended as `batch-size=<N>` on `gvadetect` (e.g. `1`) |
| `AUTOVIDEOSINK` | *(unset)* | `true` -> popup + `sink sync=true`; `false` -> headless `fakesink` |
| `DETECTION_DEVICE` | `GPU` | initial device for `/api/device` (`CPU`/`GPU`/`NPU`) |
| `UI_HOST_PORT` | `8080` | host port for the UI (Nginx) |

The friendly `AUTOVIDEOSINK=true|false` alias in the Makefile expands to
`PIPELINE_DISPLAY_VIEW=1 PIPELINE_SINK_SYNC=true` (or the false variants).

Every generated `gst-launch-1.0` command is logged at INFO by the launcher
with the prefix `[pipeline] generated cmd:` and the effective knob set
`[pipeline] knobs:`. Retrieve at any time with:

```bash
docker logs surgical-pipeline 2>&1 | grep -E 'generated cmd|knobs:' | tail -4
```

---

## Runtime lifecycle

`make up` starts the Docker stack. It does **not** start `gst-launch` —
the pipeline container waits for an explicit signal.

```bash
# 1) start the stack (add the case knobs described below)
make up SOURCE_KIND=basler SOURCE_ARG=40067928 DETECT=0 MINIMAL=1 AUTOVIDEOSINK=true

# 2) trigger inference (or press the Start button in the UI at http://localhost:8080)
curl -X POST http://localhost:8080/api/start

# 3) live latency window (rolling 200 samples)
docker exec surgical-pipeline curl -sS http://localhost:8000/latency
# or via the backend/UI proxy:
curl -sS http://localhost:8080/api/status | jq .pipeline_latency

# 4) stop / restart
curl -X POST http://localhost:8080/api/stop
curl -X POST http://localhost:8080/api/start

# 5) tear down
make down
```

Once inference starts, the UI at [http://localhost:8080](http://localhost:8080)
shows FPS, per-window latency percentiles, and CPU/GPU/NPU utilization from
the metrics collector.

---

## Discovering `SOURCE_ARG` for your Basler camera

One command:

```bash
make list-cameras
```

Sample output:

```text
[list-cameras] no /dev/video* present

Bus 004 Device 004: ID 2676:ba02 Basler AG ace

[list-cameras] Basler serials (SOURCE_ARG candidates):
  serial=40067928  model=acA1920-150uc
```

Copy the value after `serial=` into `SOURCE_ARG`. If the serial section
prints `surgical-pipeline container not running`, run `make up` once
first (the pypylon query happens inside the running container).

For `SOURCE_KIND=file`, list packaged videos on the host with
`ls -1 videos/*.mp4` and pass the in-container path
`SOURCE_ARG=/videos/<name>.mp4`.

---

## Case 1 — Basler live camera + detect + tuning (demo default)

The primary demo shape. Live Basler → tuned `gvadetect` → `gvawatermark`
→ `gvafpscounter` → preview window. This is the case the latency numbers
in the README are captured from.

```bash
make up SOURCE_KIND=basler SOURCE_ARG=40067928 DETECT=1 AUTOVIDEOSINK=true SCHEDULING_POLICY=latency BATCH_SIZE=1
curl -X POST http://localhost:8080/api/start
```

Resulting spawn (Basler feeder piped into gst-launch):

```text
python3 /opt/basler_reader.py 40067928 --geometry 1920x1080@60 --pixel-format uyvy \
| gst-launch-1.0 \
    fdsrc fd=0 blocksize=4147200 do-timestamp=true \
  ! rawvideoparse format=yuy2 width=1920 height=1080 framerate=60/1 \
  ! vapostproc ! "video/x-raw(memory:VAMemory),format=NV12" \
  ! identity \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
              device=GPU threshold=0.5 \
              pre-process-backend=va-surface-sharing \
              nireq=1 ie-config=PERFORMANCE_HINT=LATENCY \
              scheduling-policy=latency batch-size=1 \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvawatermark \
  ! gvafpscounter interval=1 \
  ! vapostproc ! "video/x-raw" \
  ! videoconvert \
  ! autovideosink sync=true
```

Confirmed live output (from container INFO log):

```text
[pipeline] knobs: detect=True watermark=True minimal=False
              scheduling_policy=latency batch_size=1 sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
FpsCounter (avg 22.20s): 58.83 fps
latency window (last 200 samples):
    mean=13.951 ms   p50=14.748 ms   p95=16.751 ms   p99=17.488 ms   max=19.707 ms
```

Notes
- `WATERMARK` is not set on the command line and defaults to `1`, so
  `gvawatermark` is present. Case 3 shows how to toggle it off.
- `SCHEDULING_POLICY=latency` and `BATCH_SIZE=1` push `gvadetect` into
  single-frame low-latency mode; drop either to compare the effect.

---

## Case 2 — Basler live camera, absolute minimum pipeline

Just the Basler source and `autovideosink`. Everything else (VA upload,
queue, identity, detect, watermark, fpscounter, sink-side VA download) is
disabled. Use this to prove camera-to-window plumbing works end to end.

```bash
make up SOURCE_KIND=basler SOURCE_ARG=40067928 DETECT=0 MINIMAL=1 AUTOVIDEOSINK=true
curl -X POST http://localhost:8080/api/start
```

Resulting spawn (Basler feeder piped into gst-launch):

```text
python3 /opt/basler_reader.py 40067928 --geometry 1920x1080@60 --pixel-format uyvy \
| gst-launch-1.0 \
    fdsrc fd=0 blocksize=4147200 do-timestamp=true \
  ! rawvideoparse format=yuy2 width=1920 height=1080 framerate=60/1 \
  ! videoconvert \
  ! autovideosink sync=true
```

Confirmed live output (from container INFO log):

```text
[pipeline] knobs: detect=False watermark=True minimal=True scheduling_policy=<unset> batch_size=None sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
```

Notes
- Passing `SCHEDULING_POLICY` or `BATCH_SIZE` in this case is a no-op —
  those are properties of `gvadetect`, and `gvadetect` is absent.
- The tracer needs a queue to publish `pipeline` latency; the truly
  minimal shape can report `available:false` until a downstream element
  settles. Use Case 3 for stable per-frame latency numbers.

---

## Case 3 — Basler live camera + detect + tuning (watermark toggleable)

Full production shape. Live Basler → tuned `gvadetect` → optional
`gvawatermark` → `gvafpscounter` → preview window. This is the case used
for latency measurement and the demo.

With watermark overlay (default):

```bash
make up SOURCE_KIND=basler SOURCE_ARG=40067928 \
        DETECT=1 WATERMARK=1 \
        SCHEDULING_POLICY=latency BATCH_SIZE=1 \
        AUTOVIDEOSINK=true
curl -X POST http://localhost:8080/api/start
```

Without watermark overlay (raw preview, same inference):

```bash
make up SOURCE_KIND=basler SOURCE_ARG=40067928 \
        DETECT=1 WATERMARK=0 \
        SCHEDULING_POLICY=latency BATCH_SIZE=1 \
        AUTOVIDEOSINK=true
curl -X POST http://localhost:8080/api/start
```

Resulting spawn with `WATERMARK=1`:

```text
python3 /opt/basler_reader.py 40067928 --geometry 1920x1080@60 --pixel-format uyvy \
| gst-launch-1.0 \
    fdsrc fd=0 blocksize=4147200 do-timestamp=true \
  ! rawvideoparse format=yuy2 width=1920 height=1080 framerate=60/1 \
  ! vapostproc ! "video/x-raw(memory:VAMemory),format=NV12" \
  ! identity \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
              device=GPU threshold=0.5 \
              pre-process-backend=va-surface-sharing \
              nireq=1 ie-config=PERFORMANCE_HINT=LATENCY \
              scheduling-policy=latency batch-size=1 \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvawatermark \
  ! gvafpscounter interval=1 \
  ! vapostproc ! "video/x-raw" \
  ! videoconvert \
  ! autovideosink sync=true
```

With `WATERMARK=0` the only difference is the `gvawatermark` element is
removed from the chain. Same detect, same tuning.

Confirmed live output (from container INFO log, `WATERMARK=1`):

```text
[pipeline] knobs: detect=True watermark=True minimal=False
              scheduling_policy=latency batch_size=1 sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
FpsCounter (avg 22.20s): 58.83 fps
latency window (last 200 samples):
    mean=13.951 ms   p50=14.748 ms   p95=16.751 ms   p99=17.488 ms   max=19.707 ms
```

---

## Verifying and retrieving results

### Live latency snapshot

```bash
docker exec surgical-pipeline curl -sS http://localhost:8000/latency
# or via the backend proxy:
curl -sS http://localhost:8080/api/status | jq .pipeline_latency
```

### Generated command + effective knobs

```bash
docker logs surgical-pipeline 2>&1 | grep -E 'generated cmd|knobs:' | tail -4
```

### Rolling latency lines from the GStreamer tracer

```bash
docker logs surgical-pipeline 2>&1 | grep 'latency window:' | tail -20
```

### Full stack health

```bash
docker compose ps
curl -sS http://localhost:8080/api/health
```

---

## Troubleshooting

**The window never opens.** `autovideosink` needs an X display reachable
from the container. Inside the container `DISPLAY=:0` and
`/tmp/.X11-unix/X0` must exist. If you are on SSH without X forwarding,
the window renders on the physical monitor attached to the host, not in
your SSH terminal. To render locally, run on the host console before
`make up`:

```bash
xhost +local:root
export DISPLAY=:0
```

If no display is available at all, drop `AUTOVIDEOSINK=true` — the
pipeline falls back to a headless `fakesink` and inference + latency
metrics still run.

**`make up` finished but no `gst-launch` in the logs.** Expected. The
launcher is idle until `POST /api/start` (or the UI Start button).

**Basler camera not visible.** Confirm from inside the container:

```bash
docker exec surgical-pipeline python3 -c "from pypylon import pylon;\
 print([(d.GetSerialNumber(), d.GetModelName())\
        for d in pylon.TlFactory.GetInstance().EnumerateDevices()])"
```

If the list is empty, replug the camera or check host USB visibility with
`lsusb -d 2676:`.

**Pipeline exits immediately after `/api/start`.** The launcher retries
once with a headless `fakesink` fallback. Check the last stderr lines:

```bash
docker logs surgical-pipeline 2>&1 | tail -60
```
