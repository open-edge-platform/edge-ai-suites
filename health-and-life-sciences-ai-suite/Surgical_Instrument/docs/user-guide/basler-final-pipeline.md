# Basler Live — Finalized Production Pipeline

This is the tuned, validated pipeline used for live Basler capture on the
Surgical Instrument suite. It is the default whenever `make up` is invoked
with `SOURCE_KIND=basler`.

## What runs

`make up SOURCE_KIND=basler SOURCE_ARG=<serial>` produces this GStreamer
pipeline (wrapped in `taskset -c 3-5 chrt -f 70` for core pinning):

```
gst-launch-1.0 \
  gencamsrc serial=<serial> pixel-format=ycbcr422_8 \
            width=1280 height=720 \
  ! vapostproc \
  ! 'video/x-raw(memory:VAMemory),format=NV12' \
  ! queue max-size-buffers=1 leaky=downstream \
  ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
              device=GPU threshold=0.5 \
              pre-process-backend=va-surface-sharing \
              nireq=1 \
              ie-config=PERFORMANCE_HINT=LATENCY \
              scheduling-policy=latency \
              batch-size=1 \
  ! queue max-size-buffers=1 leaky=downstream \
  ! gvawatermark \
  ! gvafpscounter interval=1 \
  ! vapostproc \
  ! xvimagesink sync=true
```

## Why this shape

- **`pixel-format=ycbcr422_8`** — gencamsrc emits YUV directly, so no
  `bayer2rgb` / `videoconvert` on the CPU path.
- **Single `vapostproc` upload** — one hop from system memory to VA
  surfaces (`memory:VAMemory` NV12), reused end to end.
- **`gvadetect pre-process-backend=va-surface-sharing`** — inference reads
  frames straight from the VA surface (zero-copy).
- **`scheduling-policy=latency` + `ie-config=PERFORMANCE_HINT=LATENCY`** —
  OpenVINO GPU plugin optimizes for lowest single-request latency instead
  of throughput.
- **`queue max-size-buffers=1 leaky=downstream`** — bounds each queue to at
  most one buffer and drops old frames instead of stalling. Note: buffer
  count only — do **not** add `max-size-time=...`; a time-based leak
  combined with the sink clock caused aggressive QoS frame dropping
  (collapse to ~15 fps).
- **`vapostproc ! xvimagesink sync=true`** — VA surface is downloaded /
  colour-converted at the last hop and rendered. `xvimagesink` is used
  explicitly rather than `autovideosink`: inside the container
  `autovideosink` auto-selects `kmssink`, which fails with a DRM resource
  error and crash-loops.
- **`taskset -c 3-5 chrt -f 70`** — pins gst-launch to the P-cores at
  SCHED_FIFO priority 70, removing scheduler jitter on hybrid CPUs
  (~25% higher fps vs unpinned).
- **No `frame-rate` on `gencamsrc`** — the camera free-runs at its max
  sensor rate (~120 fps here). Because the buffer timestamps match that
  rate, `sync=true` renders every frame rather than pacing down.
- **Startup GPU warmup** — the launcher runs a short camera-free
  `videotestsrc ! vapostproc ! gvadetect(GPU) ! fakesink` at container
  start (`PIPELINE_WARMUP=1`). The first GPU-inference process in a freshly
  (re)created container pays a one-time OpenVINO/GPU init cost that would
  otherwise throttle the first `/start` to ~16 fps; the warmup absorbs it
  so the first real run is already at full speed.

## Measured performance

Captured on the reference host (Basler + Intel iGPU), P-core pinned
(`taskset -c 3-5 chrt -f 70`), GPU warmed. Latency is the GStreamer
pipeline tracer (camera buffer -> sink), 200-sample rolling window.

| Case | FPS | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Finalized (this pipeline, `xvimagesink sync=true`) | ~123 | ~5.2 | ~5.2 | ~7–10 | ~11–13 | ~12–15 |
| Same, headless `fakesink` | ~122 | ~5.1 | ~5.0 | ~6.6 | ~9.7 | ~11 |
| Same, but `sync=false` (free-run) | ~123 | ~5.1 | ~5.0 | ~7.2 | ~10 | ~12 |
| First `/start` after recreate, **warmup disabled** (cold GPU) | ~16 | ~6 | ~6 | ~11 | ~13 | ~15 |

Notes:
- With the camera delivering ~120 fps and buffer timestamps at 120/1,
  `sync=true` renders ~123 fps (it is **not** capped to 60 fps). The
  dominant latency component is `gvadetect` GPU inference (~3–9 ms);
  every other element is sub-millisecond to ~1 ms.
- The ~16 fps row is the cold-start penalty when `PIPELINE_WARMUP=0`; with
  the default warmup enabled the first run is already at full speed.
- The measured latency excludes the camera's own exposure/readout and the
  physical monitor's display latency, which are outside GStreamer.

## How to run

Basic (finalized defaults, popup on the host display):

```
make up SOURCE_KIND=basler SOURCE_ARG=<serial>
```

Fixed exposure / gain (repeatable runs):

```
make up SOURCE_KIND=basler SOURCE_ARG=<serial> \
  BASLER_FIXED_CAMERA=1 BASLER_EXPOSURE_US=8000
```

Override any knob explicitly (all are optional):

| Knob | Default (basler) | Purpose |
| --- | --- | --- |
| `BASLER_PIXEL_FORMAT` | `ycbcr422_8` | camera output format |
| `PIPELINE_PREPROC_BACKEND` | `va-surface-sharing` | gvadetect preproc backend |
| `SCHEDULING_POLICY` | `latency` | OpenVINO scheduling policy |
| `BATCH_SIZE` | `1` | gvadetect batch-size |
| `PIPELINE_GST_CORES` | `3-5` | `taskset -c` cores for gst-launch |
| `PIPELINE_GST_RT_PRIORITY` | `70` | `chrt -f` SCHED_FIFO priority |
| `PIPELINE_DISPLAY_VIEW` | `1` | render popup |
| `PIPELINE_VIDEO_SINK` | `xvimagesink` | display sink element (avoid `autovideosink` -> `kmssink` crash) |
| `PIPELINE_SINK_SYNC` | `true` | clock-sync the sink (`false` = free-run, lowest latency) |
| `PIPELINE_IE_CONFIG` | `PERFORMANCE_HINT=LATENCY` | gvadetect ie-config |
| `PIPELINE_FPSCOUNTER` | `1` | insert `gvafpscounter interval=1` |
| `PIPELINE_WARMUP` | `1` | run a startup GPU warmup so the first `/start` is warm |
| `PIPELINE_WARMUP_SECONDS` | `8` | warmup duration |

Any override wins over the default:

```
make up SOURCE_KIND=basler SOURCE_ARG=<serial> \
  PIPELINE_GST_CORES=2-3 PIPELINE_GST_RT_PRIORITY=80 \
  SCHEDULING_POLICY= PIPELINE_IE_CONFIG=
```

## Verifying it after `make up`

Confirm the generated command:

```
docker exec surgical-pipeline sh -lc 'ps -o args= -C gst-launch-1.0'
```

The output should contain:
- `gencamsrc ... pixel-format=ycbcr422_8 width=1280 height=720` (no `frame-rate`)
- `vapostproc ! video/x-raw(memory:VAMemory),format=NV12`
- `gvadetect ... pre-process-backend=va-surface-sharing`
- `... ! vapostproc ! xvimagesink sync=true`
- process wrapped by `taskset -c 3-5 chrt -f 70`

Live latency + FPS (query the pipeline launcher directly):

```
docker exec surgical-pipeline sh -lc 'curl -s http://localhost:8000/health' | python3 -m json.tool
docker logs surgical-pipeline --since 60s 2>&1 | grep FpsCounter | tail -n 5
```

The `latency` object reports `mean_ms` / `p50_ms` / `p95_ms` / `p99_ms` /
`max_ms` over a 200-sample rolling window.

## Troubleshooting

- **First `/start` after `make up` / `make run` runs at ~16 fps**
  — cold GPU. The startup warmup should prevent this; if you set
  `PIPELINE_WARMUP=0`, either hit Start a second time or
  `docker restart surgical-pipeline` once to warm the GPU.
- **`A lot of buffers are being dropped` / collapse to ~15 fps**
  — a `max-size-time=...` leak on the queues combined with `sync=true`
  triggers QoS dropping. Use buffer-count-only queues
  (`queue max-size-buffers=1 leaky=downstream`).
- **`general resource error` from `GstKMSSink`**
  — `autovideosink` selected `kmssink` and it cannot take the DRM master.
  Use `PIPELINE_VIDEO_SINK=xvimagesink` (the default), or
  `PIPELINE_DISPLAY_VIEW=0` for headless benchmarking.
- **`Operation not permitted` from `chrt`**
  — the container is missing `CAP_SYS_NICE`. It is already granted in
  `docker-compose.yaml`; if you replaced the compose file, re-add
  `cap_add: [SYS_NICE]` on `surgical-pipeline`.
- **FPS lower than expected via the app but fine via `docker exec`**
  — ensure the launcher is not echoing the high-frequency latency tracer
  to the container log (handled in `latency_tracer_sink.py`); a flooded
  stderr pipe back-pressures gst-launch and throttles it.

## Related

- Pipeline builder: [pipeline/pipeline_string.py](../../pipeline/pipeline_string.py)
- Control-plane launcher: [pipeline/launcher.py](../../pipeline/launcher.py)
- Compose service definition: [docker-compose.yaml](../../docker-compose.yaml)
- Make target: [Makefile](../../Makefile) (`make up`)
