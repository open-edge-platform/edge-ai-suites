# Basler Live Pipeline — How It Works

Live polyp detection from a Basler USB3 camera, running on the Intel iGPU via
DLStreamer + OpenVINO. Driven by [`run_basler_pipeline.sh`](run_basler_pipeline.sh).

---

## 1. Why a Python bridge (no `gencamsrc`)

The DLStreamer 2026.1 image does **not** ship the Basler GStreamer plugins
(`gencamsrc` / `pylonsrc`) — verified with `gst-inspect-1.0`. Installing
Basler's Debian SDK bloats the image ~150 MB behind a registration wall.

Instead we bridge the camera with **pypylon** (already in the image):
[`pipeline/basler_reader.py`](pipeline/basler_reader.py) opens the USB camera,
configures it, grabs frames, and writes **raw bytes to stdout**. A shell pipe
feeds that stdout into `gst-launch`'s `fdsrc fd=0`.

```
basler_reader.py (pypylon) ──stdout──▶ | ──stdin(fd=0)──▶ gst-launch fdsrc
```

This is zero-dependency and portable (vs `shmsink` control sockets or a
`v4l2loopback` kernel module we don't own on customer hardware).

---

## 2. Connection chain

```mermaid
flowchart LR
    CAM["Basler acA1920-150uc<br/>USB3"] -->|USB| HOST["/dev/bus/usb"]
    HOST -->|"-v /dev/bus/usb + cgroup rule"| C[Container]
    C --> PY["basler_reader.py<br/>pypylon"]
    PY -->|raw UYVY on stdout| PIPE["shell pipe |"]
    PIPE -->|fd=0| GST[gst-launch fdsrc]
    GST --> REST[rawvideoparse → vapostproc → gvadetect ...]
```

Container access flags in the `docker run`:

| Flag | Purpose |
|------|---------|
| `-v /dev/bus/usb:/dev/bus/usb` | expose USB device nodes |
| `--device-cgroup-rule='c 189:* rmw'` | allow USB (major 189) access |
| `--device /dev/dri:/dev/dri` | reach the Intel GPU |
| `--group-add render/video` | GPU permission groups |
| `-e DISPLAY -v /tmp/.X11-unix` | X server (display mode only) |

---

## 3. The pipeline, element by element

```
basler_reader.py --pixel-format uyvy
  | gst-launch-1.0
    fdsrc fd=0 blocksize=W*H*2 do-timestamp=true
    ! rawvideoparse format=yuy2 width=W height=H framerate=FPS/1
    ! vapostproc ! "video/x-raw(memory:VAMemory),format=NV12"
    ! identity eos-after=FRAMES
    ! queue max-size-buffers=2
    ! gvadetect model=best.xml device=GPU threshold=0.5
        pre-process-backend=va-surface-sharing nireq=1
        ie-config=PERFORMANCE_HINT=LATENCY
    ! queue max-size-buffers=2
    ! gvawatermark ! gvafpscounter interval=1
    ! <SINK>            # fakesink | filesink | ximagesink
```

| Stage | What it does |
|-------|--------------|
| `basler_reader.py` | pypylon opens camera, outputs **camera-native UYVY** (FPGA debayer, 2 B/px) |
| `fdsrc fd=0` | reads one `W*H*2`-byte frame per pull; `do-timestamp` → camera is the clock |
| `rawvideoparse format=yuy2` | labels raw bytes as 1920×1080@60 (parsed as `yuy2`; UYVY parsing green-corrupts on this build) |
| `vapostproc ! VAMemory,NV12` | **GPU** UYVY→NV12; frames now live in GPU memory |
| `identity eos-after=N` | stop cleanly after N frames (no `sync=true` — camera self-paces) |
| `queue` (×2) | small bounded buffers, no `leaky` → no dropped frames, low residency |
| `gvadetect` | **zero-copy** VA surface → OpenVINO; resize 640², YOLO11n on GPU, parse boxes |
| `gvawatermark` | draws detection boxes onto the frame |
| `gvafpscounter` | prints throughput (negligible cost) |
| `<SINK>` | mode-dependent (below) |

**Why it's fast** — almost everything stays on the GPU, zero copies:
```
camera FPGA(UYVY) → GPU vapostproc(NV12) → GPU zero-copy → GPU inference
```

---

## 4. Three modes (env toggles)

| Command | Sink | Use |
|---------|------|-----|
| `bash run_basler_pipeline.sh` | `fakesink sync=false` | **measure** latency (+ trace) |
| `RECORD=1 bash run_basler_pipeline.sh` | `… ! jpegenc ! avimux ! filesink` | **record** annotated `videos/basler_output.avi` |
| `DISPLAY_VIEW=1 bash run_basler_pipeline.sh` | `… ! ximagesink` | **live window** (run from RDP/desktop GUI) |

`RECORD` and `DISPLAY_VIEW` add `vapostproc ! video/x-raw ! videoconvert`
first, because JPEG/X11 sinks can't read GPU VA surfaces — only `fakesink`
accepts them directly.

### Options (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `SERIAL` | first camera | pick a specific camera serial |
| `W` / `H` / `FPS` | 1920 / 1080 / 60 | geometry |
| `FRAMES` | 3000 | stop after N frames |
| `NIREQ` | 1 | inference requests in flight |
| `LEAKY` | 0 | 1 → `leaky=downstream max-size-buffers=1 max-size-time=16000000` (newest-frame-wins; bounds latency under a slow sink) |
| `RECORD` | 0 | 1 → save `.avi` |
| `DISPLAY_VIEW` | 0 | 1 → live window |
| `VSINK` | `ximagesink` | display sink (RDP-safe default) |
| `OUT_AVI` | `/videos/basler_output.avi` | record path (container-side) |

Every run prints a per-element table plus:
- `compute critical path (gva* sum)` — inference + watermark only.
- `E2E PIPELINE (fdsrc->fakesink)` in MEASURE mode, or
  `CAMERA-TO-SCREEN (fdsrc->display)` in DISPLAY mode (the sink is a real display).

Examples:
```bash
# Measure pipeline latency (fakesink)
bash run_basler_pipeline.sh

# Live view, freshest-frame-wins (recommended for a live feed)
DISPLAY_VIEW=1 LEAKY=1 FRAMES=3000 bash run_basler_pipeline.sh

# Live view, keep every frame (shows backlog under a slow RDP sink)
DISPLAY_VIEW=1 LEAKY=0 FRAMES=3000 bash run_basler_pipeline.sh

# Record an annotated clip
SERIAL=40067928 RECORD=1 FRAMES=1200 bash run_basler_pipeline.sh
```

### Live display commands + results

Two commands produce a live window with detection boxes (run from the RDP /
desktop GUI terminal). Both use `LEAKY=1` (freshest-frame-wins) and let
`autovideosink` pick a hardware sink.

**1. Full path** (keeps `gvafpscounter` + GPU→system download):

```bash
VSINK=autovideosink DISPLAY_VIEW=1 LEAKY=1 bash run_basler_pipeline.sh
```

Generated pipeline:

```bash
python3 /opt/basler_reader.py --geometry 1920x1080@60 --pixel-format uyvy \
  | gst-launch-1.0 \
    fdsrc fd=0 blocksize=4147200 do-timestamp=true ! \
    rawvideoparse format=yuy2 width=1920 height=1080 framerate=60/1 ! \
    vapostproc ! "video/x-raw(memory:VAMemory),format=NV12" ! \
    identity eos-after=3000 ! \
    queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream ! \
    gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml device=GPU threshold=0.5 \
      pre-process-backend=va-surface-sharing nireq=1 ie-config=PERFORMANCE_HINT=LATENCY ! \
    queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream ! \
    gvawatermark ! gvafpscounter interval=1 ! \
    vapostproc ! "video/x-raw" ! videoconvert ! autovideosink sync=false
```

Result:

```
element               samples   mean_ms   p99_ms
------------------------------------------------
gvadetect0               2920    10.315   15.359 *
gvawatermarkimpl0        2999     0.054    0.123 *
gvafpscounter0           2999     0.024    0.068 *
rawvideoparse0           3000     3.960    6.320
vapostproc0              3000     4.328    6.152
videoconvert0            2999     0.010    0.032
------------------------------------------------
compute critical path (gva* sum)          10.393 ms
CAMERA-TO-SCREEN (fdsrc->display) mean    12.910 ms
CAMERA-TO-SCREEN (fdsrc->display) p50/p99   16.41 / 20.37 ms
```

**2. Minimal path** (`MINIMAL=1` — drops `gvafpscounter` + `videoconvert`, keeps
one `vapostproc` bridge; a bare `gvawatermark ! sink` fails `not-negotiated`):

```bash
MINIMAL=1 VSINK=autovideosink DISPLAY_VIEW=1 LEAKY=1 bash run_basler_pipeline.sh
```

Generated pipeline:

```bash
python3 /opt/basler_reader.py --geometry 1920x1080@60 --pixel-format uyvy \
  | gst-launch-1.0 \
    fdsrc fd=0 blocksize=4147200 do-timestamp=true ! \
    rawvideoparse format=yuy2 width=1920 height=1080 framerate=60/1 ! \
    vapostproc ! "video/x-raw(memory:VAMemory),format=NV12" ! \
    identity eos-after=3000 ! \
    queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream ! \
    gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml device=GPU threshold=0.5 \
      pre-process-backend=va-surface-sharing nireq=1 ie-config=PERFORMANCE_HINT=LATENCY ! \
    queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream ! \
    gvawatermark ! vapostproc ! autovideosink sync=false
```

Result:

```
element               samples   mean_ms   p99_ms
------------------------------------------------
gvadetect0               2908    10.265   15.022 *
gvawatermarkimpl0        2999     0.058    0.137 *
vapostproc0              3000     2.599    4.747
vapostproc1              2999     0.029    0.085
------------------------------------------------
compute critical path (gva* sum)          10.323 ms
CAMERA-TO-SCREEN (fdsrc->display) mean    12.634 ms
CAMERA-TO-SCREEN (fdsrc->display) p50/p99   13.73 / 17.89 ms
```

**Comparison**

| Command | camera-to-screen mean | p99 | note |
|---------|----------------------:|----:|------|
| Full (`autovideosink`) | 12.910 ms | 20.37 | keeps fpscounter + videoconvert |
| **Minimal (`MINIMAL=1`)** | **12.634 ms** | **17.89** | leanest; slightly lower + tighter p99 |

> Over RDP with software `ximagesink` the same run is ~33 ms (the extra ~12 ms
> is `videoconvert` for the software sink). A hardware sink removes it.
> Use `MINIMAL=1` on a real monitor; keep the default (full) path for RDP
> `ximagesink`.

---

## 5. Latency (measured)

Three numbers matter, at increasing scope:

| Metric | Value | Scope |
|--------|------:|-------|
| Model inference (`benchmark_app`) | **4.46 ms** / 224 FPS | model only, no GStreamer |
| Compute critical path (`gva*` sum) | **~11 ms** | inference + watermark |
| E2E pipeline (`fdsrc → fakesink`) | **~13–16 ms** | whole graph, no display |

Per-element (MEASURE mode, camera self-paced, `flags=pipeline+element`):

| Stage | mean ms | note |
|-------|--------:|------|
| rawvideoparse0 | ~2–4 | camera frame arrival (pacing, **not** compute) |
| vapostproc0 (UYVY→NV12) | ~2–3 | real per-frame GPU input convert |
| gvadetect0 | ~8–11 | preprocess + inference + YOLO parse |
| gvawatermark | ~0.05 | cheap (few boxes in bench scene) |

### Leaky vs non-leaky — DISPLAY mode over RDP (3000 frames)

`leaky=downstream` (`LEAKY=1`) drops stale frames instead of letting them pile
up behind a slow sink. Measured with the live camera → `ximagesink` over RDP:

| Metric | `LEAKY=0` | `LEAKY=1` | Δ |
|--------|----------:|----------:|----:|
| **camera-to-screen mean** | **72.30 ms** | **33.03 ms** | **−54 %** |
| camera-to-screen p50 | 68.71 | 34.71 | −49 % |
| camera-to-screen p99 | 110.19 | 43.95 | −60 % |
| `queue1` (pre-sink backlog) | 40.77 | 8.01 | frames dropped, not queued |
| `queue0` | 12.59 | 0.08 | relieved |

**Takeaway:** for a **live feed**, `LEAKY=1` is the correct choice — it roughly
**halves** camera-to-screen latency and tames the p99, at the cost of dropping
stale frames (freshest-frame-wins). For pure **throughput/measurement** (process
every frame) leave `LEAKY=0`.

> Of the ~33 ms leaky camera-to-screen, ~12 ms is `videoconvert` (NV12→RGB for
> **software** `ximagesink`) — an **RDP-only** cost. On a real HDMI monitor with
> a hardware/GL sink that ~12 ms + the network path largely vanish, so
> camera-to-screen drops toward ~20 ms (still excluding sensor exposure + USB).

### What these numbers do NOT include (glass-to-glass)

The GStreamer tracer measures `fdsrc → sink` only. **True camera-to-screen
(glass-to-glass) also includes** the sensor exposure/readout (~8–16 ms) and
USB3 transfer (before `fdsrc`), plus the physical panel scanout (after the
sink). Full glass-to-glass on a real monitor is therefore ~**35–50 ms**
(consistent with the 39–55 ms medical-endoscope reference). Measuring that
requires a physical **LED + high-speed-camera** test, not this tracer.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `no element gencamsrc` | plugin not in image | expected — we use the pypylon bridge |
| Display "stuck", no window | `autovideosink` picks Xv/GL which fail over RDP | default `VSINK=ximagesink` (already set) |
| `DISPLAY is empty` | plain SSH shell | run from the RDP/desktop GUI terminal || live view laggy / high latency over RDP | frames pile up behind slow software `ximagesink` | use `LEAKY=1` (drops stale frames, ~2\u00d7 lower camera-to-screen); or use a real HDMI monitor + `VSINK=glimagesink` || fps below 60 in bench | auto-exposure under dim office light | real scope light source is bright → hits 60 |
| `.avi` owned by root | Docker wrote it | `sudo chown $USER:$USER videos/basler_output.avi` |
| camera not found | USB access / power | check `lsusb \| grep 2676` (Basler VID) |

Stop a run early: `Ctrl+C`, or from another terminal `docker ps` → `docker kill <id>`.

---

## 7. Relation to production

Production ([`pipeline/pipeline_string.py`](pipeline/pipeline_string.py), source
kind `basler`) uses the **same** bridge + GPU path, driven by
[`pipeline/launcher.py`](pipeline/launcher.py) inside the `surgical-pipeline`
container. `run_basler_pipeline.sh` is a **standalone** version for
benchmarking, recording, and live viewing without the full stack.
