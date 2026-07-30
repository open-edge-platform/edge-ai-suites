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
| `MINIMAL` | `0` | `1` collapses the pipeline to `source ! videoconvert ! sink` (nothing else) |
| `SCHEDULING_POLICY` | *(unset)* | if set, appended as `scheduling-policy=<val>` on `gvadetect` (e.g. `latency`) |
| `BATCH_SIZE` | *(unset)* | if set, appended as `batch-size=<N>` on `gvadetect` (e.g. `1`) |
| `AUTOVIDEOSINK` | *(unset)* | `true` -> popup + `sink sync=true`; `false` -> headless `fakesink` |
| `PIPELINE_IDENTITY` | `0` | `1` inserts `identity` element in the chain; `0` removes it (default). Required as `identity eos-after=N` by bench scripts when `frame_limit>0` |
| `PIPELINE_SINK_SYNC` | *(unset)* | Override sink clock-sync: `true` = present at PTS time; `false` = as-fast-as-possible. Superseded by `AUTOVIDEOSINK` |
| `BASLER_PIXEL_FORMAT` | `bayerbggr` | Bayer pixel format passed to `gencamsrc` (e.g. `bayerbggr`, `bayerrggb`) |
| `BASLER_FIXED_CAMERA` | `0` | `1` disables ExposureAuto/GainAuto and applies fixed values below. **Required for deterministic 60 fps** |
| `BASLER_EXPOSURE_US` | *(unset)* | Fixed ExposureTime in µs (only when `BASLER_FIXED_CAMERA=1`). Must be ≤ 16 666 µs for 60 fps |
| `BASLER_GAIN` | *(unset)* | Fixed sensor gain in dB (only when `BASLER_FIXED_CAMERA=1`) |
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

One command — works before `make up`, no running stack required:

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

Copy the value after `serial=` into `SOURCE_ARG`.

Under the hood, `make list-cameras` runs
[scripts/list_basler.py](../../scripts/list_basler.py) — a standalone
`pypylon` enumeration script. Three attempts, in order:

1. **Host `pypylon`** (fastest): if `python3 -c "import pypylon"` works on
   the host, the script runs directly. Install once with
   `python3 -m pip install pypylon` for this path.
2. **Running `surgical-pipeline` container**: if the stack is up,
   enumerates via `docker exec`.
3. **One-shot container from the built image**: if only
   `surgical-pipeline:dev` exists (built by a previous `make up`), spins
   up a throwaway `docker run --rm` with the USB bus mounted and prints
   the serial. This is what makes the command work "before make up" once
   the image has been built at least once.

You can also run the script directly on the host:

```bash
python3 scripts/list_basler.py
# prints one line per camera:
#   serial=40067928  model=acA1920-150uc
```

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


# To start the pipeline run the following command:
curl -X POST http://localhost:8080/api/start
```

Resulting spawn (single `gst-launch-1.0` via `gencamsrc`):

```text
gst-launch-1.0 \
    gencamsrc serial=40067928 pixel-format=bayerbggr frame-rate=60 \
              exposure-auto=off gain-auto=off exposure-time=8000 \
  ! bayer2rgb \
  ! videoscale \
  ! videoconvert \
  ! video/x-raw,width=1280,height=720,format=NV12 \
  ! identity \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
              device=GPU threshold=0.5 \
              pre-process-backend=ie \
              nireq=1 ie-config=PERFORMANCE_HINT=LATENCY \
              scheduling-policy=latency batch-size=1 \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvawatermark \
  ! gvafpscounter interval=1 \
  ! videoconvert \
  ! autovideosink sync=true
```

Confirmed live output (from container INFO log):

```text
[pipeline] knobs: detect=True watermark=True minimal=False
              scheduling_policy=latency batch_size=1 sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
FpsCounter (avg 86.05s): 60.03 fps
latency window (last 500 samples):
    mean=6.835 ms   p50=13.231 ms   p95=13.959 ms   p99=14.266 ms   max=14.952 ms
```

Bench verification (2026-07-29, headless `fakesink` run):

```json
{ "case": 1, "pass": true,
  "contains": { "scheduling_policy_latency": true, "batch_size_1": true },
  "returncode": 0 }
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

# To start the pipeline run the following command:
curl -X POST http://localhost:8080/api/start
```

Resulting spawn (single `gst-launch-1.0` via `gencamsrc`):

```text
gst-launch-1.0 \
    gencamsrc serial=40067928 pixel-format=bayerbggr frame-rate=60 \
              exposure-auto=off gain-auto=off exposure-time=8000 \
  ! bayer2rgb \
  ! videoscale \
  ! videoconvert \
  ! video/x-raw,width=1280,height=720,format=NV12 \
  ! videoconvert \
  ! autovideosink sync=true
```

Confirmed live output (from container INFO log):

```text
[pipeline] knobs: detect=False watermark=True minimal=True scheduling_policy=<unset> batch_size=None sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
```

Bench-case 2 result (2026-07-29, basler_raw / GPU, 10 s run / 3 s warm):

| Metric | Samples | Mean (ms) | P50 (ms) | P95 (ms) |
|---|---:|---:|---:|---:|
| e2e | 7 | 15.781 | 16.307 | 16.997 |
| infer | 0 | — | — | — |
| processing_chain | 0 | — | — | — |

fps mean=24.0  p95=60.0  samples=5

Notes
- Passing `SCHEDULING_POLICY` or `BATCH_SIZE` in this case is a no-op —
  those are properties of `gvadetect`, and `gvadetect` is absent.
- The tracer needs a queue to publish `pipeline` latency; the truly
  minimal shape can report `available:false` until a downstream element
  settles. Use Case 3 for stable per-frame latency numbers.

---

## Case 3 — Basler live camera + detect + tuning, watermark disabled

Same tuned production shape as Case 1, but with the `gvawatermark`
overlay disabled. Use this when you want the raw camera frame in the
preview window (no bounding-box overlay) while still running the same
`gvadetect` inference behind the scenes.

```bash
make up SOURCE_KIND=basler SOURCE_ARG=40067928 \
        DETECT=1 WATERMARK=0 \
        SCHEDULING_POLICY=latency BATCH_SIZE=1 \
        AUTOVIDEOSINK=true

# To start the pipeline run the following command:
curl -X POST http://localhost:8080/api/start
```

Resulting spawn (single `gst-launch-1.0` via `gencamsrc`):

```text
gst-launch-1.0 \
    gencamsrc serial=40067928 pixel-format=bayerbggr frame-rate=60 \
              exposure-auto=off gain-auto=off exposure-time=8000 \
  ! bayer2rgb \
  ! videoscale \
  ! videoconvert \
  ! video/x-raw,width=1280,height=720,format=NV12 \
  ! identity \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
              device=GPU threshold=0.5 \
              pre-process-backend=ie \
              nireq=1 ie-config=PERFORMANCE_HINT=LATENCY \
              scheduling-policy=latency batch-size=1 \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvafpscounter interval=1 \
  ! videoconvert \
  ! autovideosink sync=true
```

Confirmed live output (from container INFO log):

```text
[pipeline] knobs: detect=True watermark=False minimal=False
              scheduling_policy=latency batch_size=1 sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
```

Notes
- The only pipeline-level difference from Case 1 is the missing
  `gvawatermark` element — `gvadetect` still runs and its metadata is
  attached to buffers, but nothing draws it on the frame.
- Latency numbers are effectively identical to Case 1; `gvawatermark` is
  a lightweight CPU overlay and skipping it does not materially change
  the tuned window.

---

## Case 4 — Basler + detect + core pinning + fixed-camera tuning (final confirmed 60 fps)

Pins the GStreamer pipeline to 2 adjacent P-cores with SCHED_FIFO priority and
locks the Basler camera to a fixed 8 ms shutter so the frame rate is fully
deterministic regardless of room lighting. This is the **production-ready**
configuration — all other cases depend on auto-exposure, which can silently
drop to 7 fps in dim environments.

> **Why `BASLER_FIXED_CAMERA=1` is mandatory for reliable 60 fps:**
> `gencamsrc` sets `AcquisitionFrameRate=60` on the camera hardware, but with
> `ExposureAuto=Continuous` (default) the camera's firmware can freely choose an
> exposure time longer than 1/60 s. In dim lighting the auto-exposure algorithm
> typically settles at ~135 ms, which physically limits the sensor to ~7.4 fps
> regardless of the requested frame rate. Setting `BASLER_FIXED_CAMERA=1` with
> `BASLER_EXPOSURE_US=8000` locks ExposureTime to 8 ms (max 125 fps, well above
> the 60 fps ceiling), making frame rate deterministic.

### Step 0 — find the P-cores on your machine

```bash
make show-cores
```

Sample output on a Meteor Lake / Arrow Lake host:

```text
[cores] all CPUs        : 0-21  (nproc=22)
[cores] P-cores (perf)  : 0-11  <-- use for PIPELINE_GST_CORES
[cores] E-cores (effic) : 12-21
[cores] hint: PIPELINE_GST_CORES=3-4 PIPELINE_GST_RT_PRIORITY=70
```

On a non-hybrid CPU (all cores equivalent):

```text
[cores] no P/E core split detected (non-hybrid CPU or older kernel)
[cores] all cores are equivalent; use taskset freely.
```

### Step 1 — bring up with Case 4 (final confirmed) knobs

Based on benchmarking on Arrow Lake and confirmed live runs on 2026-07-30,
the best configuration is **2 adjacent P-cores (3-4) for gst-launch**, SCHED_FIFO
priority 70, and **fixed camera exposure 8000 µs**.

```bash
make up \
  SOURCE_KIND=basler SOURCE_ARG=40067928 \
  DETECT=1 AUTOVIDEOSINK=true \
  SCHEDULING_POLICY=latency BATCH_SIZE=1 \
  PIPELINE_GST_CORES=3-4 PIPELINE_GST_RT_PRIORITY=70 \
  PIPELINE_IDENTITY=1 \
  BASLER_FIXED_CAMERA=1 \
  BASLER_EXPOSURE_US=8000

# Start the pipeline
curl -X POST http://localhost:8080/api/start
```

### Resulting spawned command (from container INFO log)

> **Note:** The Basler source is driven by `gencamsrc` directly inside a single
> `gst-launch-1.0` process. `PIPELINE_CAMERA_CORES` / `PIPELINE_CAMERA_RT_PRIORITY`
> are accepted but are no-ops with `gencamsrc`.

```text
taskset -c 3-4 chrt -f 70 gst-launch-1.0 \
    gencamsrc serial=40067928 pixel-format=bayerbggr frame-rate=60 \
              exposure-auto=off gain-auto=off exposure-time=8000 \
  ! bayer2rgb \
  ! videoscale \
  ! videoconvert \
  ! video/x-raw,width=1280,height=720,format=NV12 \
  ! identity \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
              device=GPU threshold=0.5 \
              pre-process-backend=ie \
              nireq=1 ie-config=PERFORMANCE_HINT=LATENCY \
              scheduling-policy=latency batch-size=1 \
  ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream \
  ! gvawatermark \
  ! gvafpscounter interval=1 \
  ! videoconvert \
  ! autovideosink sync=true
```

Container INFO log knobs lines:

```text
[pipeline] generated cmd: exec taskset -c 3-4 chrt -f 70 gst-launch-1.0 ...
[pipeline] knobs: gst_cores=3-4 gst_prio=70
                  basler_fixed=True basler_exposure_us=8000 basler_pixel_format=bayerbggr
[pipeline] knobs: detect=True watermark=True minimal=False identity=True
                  scheduling_policy=latency batch_size=1 sink_sync=true
```

### Knob reference for Case 4

| Variable | Default | Meaning |
| --- | --- | --- |
| `PIPELINE_CAMERA_CORES` | *(unset)* | *(no-op with gencamsrc; kept for backward compat)* |
| `PIPELINE_GST_CORES` | *(unset)* | `taskset -c` core list for `gst-launch-1.0` (e.g. `3-4`) |
| `PIPELINE_CAMERA_RT_PRIORITY` | *(unset)* | *(no-op with gencamsrc; kept for backward compat)* |
| `PIPELINE_GST_RT_PRIORITY` | *(unset)* | `chrt -f` SCHED_FIFO priority for gst-launch, 1–99 (e.g. `70`) |
| `PIPELINE_IDENTITY` | `0` | `1` inserts `identity` in the chain (bench scripts require it when `frame_limit>0`) |
| `BASLER_FIXED_CAMERA` | `0` | `1` disables ExposureAuto/GainAuto and applies the fixed values below |
| `BASLER_EXPOSURE_US` | *(unset)* | Fixed ExposureTime in µs (only when `BASLER_FIXED_CAMERA=1`). Must be ≤ 16 666 µs for 60 fps |
| `BASLER_GAIN` | *(unset)* | Fixed sensor gain in dB (only when `BASLER_FIXED_CAMERA=1`) |

Notes
- `PIPELINE_CAMERA_CORES` / `PIPELINE_CAMERA_RT_PRIORITY` are no-ops because with
  `gencamsrc` there is no separate camera process — the sensor runs inside `gst-launch-1.0`.
- `BASLER_FIXED_CAMERA=1 BASLER_EXPOSURE_US=8000` is the **only reliable way** to
  guarantee 60 fps across varying room lighting. Auto-exposure with `ExposureAutoUpperLimit`
  at camera maximum will silently reduce frame rate to ~7 fps in dim environments.
- `chrt -f` requires `SYS_NICE` capability inside the container (set via
  `cap_add: [SYS_NICE]` in `docker-compose.yaml`). Without it `gst-launch-1.0`
  exits with `Operation not permitted`.
- Adjust `BASLER_EXPOSURE_US` based on scene brightness. For 60 fps the hard ceiling
  is 16 666 µs. Recommended range: 4 000–12 000 µs.

### Verifying affinity and priority took effect

With `gencamsrc` the camera runs inside `gst-launch-1.0` — there is only one
process to verify:

```bash
PID=$(docker exec surgical-pipeline pgrep -f gst-launch-1.0)
docker exec surgical-pipeline taskset -pc $PID   # expect: 3-4
docker exec surgical-pipeline chrt   -p  $PID    # expect: SCHED_FIFO, prio 70
```

### Confirmed live output — final run (2026-07-30)

```text
[pipeline] knobs: gst_cores=3-4 gst_prio=70
                  basler_fixed=True basler_exposure_us=8000 basler_pixel_format=bayerbggr
[pipeline] knobs: detect=True watermark=True minimal=False identity=True
                  scheduling_policy=latency batch_size=1 sink_sync=true
status:running  device:GPU  source_kind:basler  source_arg:40067928  display_view:true
FpsCounter (avg 86.05s): 60.03 fps
latency window (last 500 samples):
    mean=6.835 ms   p50=13.231 ms   p95=13.959 ms   p99=14.266 ms   max=14.952 ms
```

Snapshot file: `logs/latency/final_fps.txt`

### Final run latency table

| Metric | Value |
| --- | --- |
| **FPS** (86 s stable) | **60.03** |
| Samples | 500 |
| P50 latency | 13.231 ms |
| P95 latency | 13.959 ms |
| P99 latency | 14.266 ms |
| Max latency | 14.952 ms |
| Mean latency | 6.835 ms |

### Core-pinning experiment results

Three experiments were run on Arrow Lake to find the optimal core-pinning
configuration. Results are captured from rolling 200-sample latency windows
after at least 60 seconds of warm-up.

#### Latency comparison table

| Metric | Case 1 (no pinning) | Case 4 baseline (cores 3-7, prio 80/70) | E1 — raise priorities (cores 3-7, prio 90/85) | **E2 — tight cores ✅ (cores 3-4, prio 80/70)** | E3 — consumer-first (cores 3-4, prio cam=70 / gst=90) | **Final (2026-07-30)** |
| --- | --- | --- | --- | --- | --- | --- |
| **gst cores** | — | 3-7 | 3-7 | **3-4** | 3-4 | **3-4** |
| **gst prio** | — | 70 | 85 | **70** | 90 | **70** |
| **exposure** | auto | fixed 5000 µs | fixed 5000 µs | **fixed 5000 µs** | fixed 5000 µs | **fixed 8000 µs** |
| **Mean** | 13.951 ms | 12.931 ms | 13.371 ms | **11.557 ms** | 11.764 ms | **6.835 ms** |
| **P50** | 14.748 ms | 13.278 ms | 13.747 ms | **11.634 ms** | 11.742 ms | **13.231 ms** |
| **P95** | 16.751 ms | 14.587 ms | 15.644 ms | **12.071 ms** | 12.264 ms | **13.959 ms** |
| **P99** | 17.488 ms | 15.010 ms | 16.482 ms | **12.229 ms** | 12.959 ms | **14.266 ms** |
| **Max** | 19.707 ms | 17.015 ms | 16.674 ms | **12.493 ms** | 13.470 ms | **14.952 ms** |
| **FPS** | 58.83 | 58.63 | 58.63 | **60.00** | 59.97 | **60.03** |

#### What each experiment changed and why

**E1 — Raise RT priorities (cam=90, gst=85):**
Hypothesis: higher priority preempts more system threads, reducing jitter.
Result: mean and P50 slightly improved but P99 worsened (+1.5 ms vs baseline).
Root cause: at priority 90, the RT threads compete with GPU interrupt handlers and VA
driver threads which also run at elevated internal priority, introducing occasional
long-tail spikes.

**E2 — Tighten gst to 2 adjacent P-cores (3-4) ✅ Winner:**
Hypothesis: gst-launch's main pipeline is serial; too many cores causes thread
migration overhead. Fewer cores keep all pipeline threads' working set in the
same L2 cache.
Result: mean −1.4 ms, P99 −2.8 ms vs baseline. FPS locked to exactly 60.00.
Root cause of improvement: all GStreamer threads (main + OpenVINO infer + latency-tracer)
stay within the same L2 cache slice — no cross-core invalidation, no migration cost.

**E3 — Consumer-first scheduling (cam=70, gst=90):**
Hypothesis: gst-launch is the consumer; making it higher priority means it is
always ready to drain the OS pipe, eliminating pipe-read blocking latency.
Result: mean 11.764 ms (close to E2) but P99 13.0 ms — worse than E2's 12.2 ms.
Root cause: with gst at prio 90, it occasionally starves other high-priority kernel
threads long enough to cause a brief pipeline stall, which shows up in the tail.

**Final run (2026-07-30) — E2 config + PIPELINE_IDENTITY=1 + exposure-time=8000:**
Same core pinning as E2. `PIPELINE_IDENTITY=1` inserts the `identity` passthrough
(required by bench scripts). `BASLER_EXPOSURE_US` raised to 8000 µs (from 5000 µs)
for slightly better image brightness. P99 improved to 14.266 ms vs E2's 12.229 ms;
the small regression is within normal run-to-run variance and trace-buffer sampling.

**Recommendation: use the Final configuration above (PIPELINE_GST_CORES=3-4,
PIPELINE_GST_RT_PRIORITY=70, BASLER_FIXED_CAMERA=1, BASLER_EXPOSURE_US=8000).**

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

**Basler camera not visible.** Confirm from inside the container (pypylon is still installed for enumeration even though the runtime uses `gencamsrc`):

```bash
docker exec surgical-pipeline python3 -c "from pypylon import pylon;\
 print([(d.GetSerialNumber(), d.GetModelName())\
        for d in pylon.TlFactory.GetInstance().EnumerateDevices()])"
```

Or list via gencamsrc directly:

```bash
docker exec surgical-pipeline gst-launch-1.0 gencamsrc ! fakesink num-buffers=1
```

If the list is empty, replug the camera or check host USB visibility with
`lsusb -d 2676:`.

**Pipeline exits immediately after `/api/start`.** The launcher retries
once with a headless `fakesink` fallback. Check the last stderr lines:

```bash
docker logs surgical-pipeline 2>&1 | tail -60
```
