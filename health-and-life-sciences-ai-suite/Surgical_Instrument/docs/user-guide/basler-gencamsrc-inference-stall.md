# Basler `gencamsrc` + `gvadetect` Inference Stall — Problem & Solution

## Summary

On some Basler cameras / iGPU hosts, the direct `gencamsrc` live pipeline
collapses to **~11–13 FPS** the moment `gvadetect` (GPU inference) is added,
while the CPU and iGPU sit **mostly idle**. The camera alone and inference
alone are both fast; only the *combination* stalls.

The fix is to **decouple camera acquisition from the GStreamer pipeline** by
reading frames through `basler_reader.py` and piping them into `fdsrc`. This
copies each frame into clean system memory before it reaches `gvadetect`,
which removes the stall and restores full inference throughput
(**~11 FPS → ~45 FPS**, a 4x improvement, on the affected machine).

- Affected camera in this investigation: **Basler daA1920-160uc** (dart, USB3).
- Host: Intel iGPU (`iHD` VA driver, Gen Graphics), DL Streamer container.

---

## Problem

### Symptom

```text
FpsCounter(average 3.69sec): total=13.00 fps, number-streams=1, per-stream=13.00 fps
```

- Reported FPS is stuck at ~11–13.
- `intel_gpu_top` / CPU usage show the system **underutilized** — it is not
  compute-bound, it is **blocking** (~77 ms per frame with idle silicon).
- Happens on the same git branch that runs at 120+ FPS on the reference host.

### What we measured (isolation tests)

Each stage was benchmarked independently on the affected machine:

| Pipeline | FPS | Notes |
| --- | ---: | --- |
| `gencamsrc → fakesink` | ~82 | Camera acquisition is healthy |
| `gencamsrc → vapostproc → system NV12 → fakesink` | ~82 | VA convert to system memory is fine |
| `gencamsrc → vapostproc → VAMemory NV12 → fakesink` | ~10 | VAMemory export stalls (without normalize) |
| `gencamsrc → videoconvert(passthrough) → vapostproc → VAMemory → fakesink` | ~83 | Normalize fixes the VAMemory export |
| **`gencamsrc → … → gvadetect` (va-surface-sharing)** | **~11** | Stall re-appears with inference |
| **`gencamsrc → … → gvadetect` (opencv)** | **~11** | Also stalls — not backend-specific |
| `videotestsrc (is-live=true) → vapostproc → VAMemory → gvadetect` | ~82 | Live source + inference is fine |
| `videotestsrc → gvadetect` (customer) | ~160 | Inference alone is fast |
| **`basler_reader.py \| fdsrc → … → gvadetect`** | **~45** | **Decoupled reader removes the stall** |

### Root cause

The stall is specific to **`gencamsrc`-originated buffers reaching
`gvadetect`**. It is **not**:

- the camera (raw capture hits 82 FPS),
- the preprocessing backend (both `va-surface-sharing` and `opencv` stall),
- VAMemory vs system memory (both stall once inference consumes the frame),
- source liveness (`videotestsrc is-live=true` + inference runs full speed).

`gencamsrc` delivers buffers backed by the camera's USB/GenTL DMA memory.
Any stage that makes a real consumer **fully read the pixels** of such a
buffer — CPU color-convert, `opencv` preprocessing, or GPU inference via an
imported VA surface — runs at ~11 FPS. Stages that do **not** fully read the
pixels (`fakesink`, a same-format `videoconvert` passthrough) stay fast. The
per-frame read of that camera-backed memory blocks for ~77 ms with the
compute engines idle, which is the classic signature of reading from
non-cached / write-combined device memory rather than a compute limit.

The reference host does not exhibit this because its camera/driver/iGPU
combination imports those buffers cheaply; the affected daA1920-160uc + iGPU
combination does not.

---

## Solution

### Decouple acquisition with `basler_reader.py | fdsrc`

Instead of `gencamsrc` feeding the pipeline directly, run the existing
[`pipeline/basler_reader.py`](../../pipeline/basler_reader.py) bridge. It
grabs frames with pypylon and writes raw bytes to stdout; `fdsrc` then feeds
the pipeline. The stdout copy lands each frame in **normal, cacheable system
memory**, severing the camera's slow DMA memory before `gvadetect` reads it.

This is the same decoupled shape the project used previously (before the
switch to direct `gencamsrc`) and is proven to deliver full inference FPS.

### Validated command (headless, on the affected machine)

```bash
python3 /opt/basler_reader.py <SERIAL> --geometry 1280x720@60 --pixel-format uyvy \
| gst-launch-1.0 \
    fdsrc fd=0 blocksize=1843200 do-timestamp=true \
    ! rawvideoparse format=uyvy width=1280 height=720 framerate=60/1 \
    ! vapostproc \
    ! "video/x-raw(memory:VAMemory),format=NV12" \
    ! queue max-size-buffers=2 leaky=downstream \
    ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
        device=GPU threshold=0.5 pre-process-backend=va-surface-sharing \
        nireq=4 batch-size=1 \
    ! queue max-size-buffers=2 leaky=downstream \
    ! gvafpscounter interval=1 \
    ! fakesink sync=false async=false
```

- `blocksize = width × height × 2` for UYVY (1280 × 720 × 2 = **1 843 200**).
- Result: **~45 FPS with inference**, vs ~11 FPS for direct `gencamsrc`.

### Result

| Configuration | FPS with inference |
| --- | ---: |
| Direct `gencamsrc → gvadetect` | ~11 |
| `basler_reader.py \| fdsrc → gvadetect` | ~45 |

The stall is eliminated. `gvadetect` is no longer the bottleneck.

---

## Remaining ceiling (next optimization, not the bug)

After the fix, throughput is capped at **~45 FPS by the Python reader**, not
by inference. Two contributing factors, both in
[`pipeline/basler_reader.py`](../../pipeline/basler_reader.py):

1. **Frame-rate node not applied on the dart camera.** The reader sets
   `AcquisitionFrameRateAbs` (the acA/ace node). The daA1920-160uc (dart)
   uses `AcquisitionFrameRateEnable=true` + `AcquisitionFrameRate`, so the
   set fails (`LogicalErrorException`) and the camera free-runs under
   auto-exposure. Requesting `@60` vs `@120` makes no difference (~45 FPS
   either way), confirming the requested rate is not the lever.
2. **Per-frame Python overhead.** Grabbing one frame at a time and writing
   via the numpy `GetArray()` + `sys.stdout.buffer.write` path costs enough
   per 1.84 MB frame to cap the loop near 45 FPS.

Proposed follow-up (raises the reader toward 60–82 FPS):

- Set the correct dart frame-rate node with a fallback to the acA node.
- Write the raw grab buffer with `os.write(1, memoryview(grab.GetBuffer()))`
  and increase `MaxNumBuffer` with `GrabStrategy_OneByOne`.

---

## Recommended productization

Add a source-ingest knob so the app selects the working path automatically:

- `BASLER_INGEST=reader|gencamsrc` (default `reader` for affected cameras) in
  [`pipeline/pipeline_string.py`](../../pipeline/pipeline_string.py) and
  [`pipeline/launcher.py`](../../pipeline/launcher.py).
- Keep direct `gencamsrc` available for hosts where it already runs fast.

---

## How to reproduce / diagnose on a new machine

1. **Free the camera first** — the app launcher (`/opt/launcher.py`) holds
   the Basler. Stop it before manual tests:
   ```bash
   docker exec surgical-pipeline sh -lc 'curl -s -X POST http://localhost:8000/stop; echo'
   # if still held, the launcher is PID 1 after a fresh container; recreate:
   docker compose -f docker-compose.yaml down surgical-pipeline
   docker compose -f docker-compose.yaml up -d surgical-pipeline
   ```
   > The `Failed to load transport layer ... U3V/GEV ... already in use`
   > warnings are **harmless** and appear even on healthy runs. The real
   > "camera busy" error is `gencamsrc ... Exception: Feature not writable: Width`.

2. **Confirm the camera is free** (~82 FPS expected):
   ```bash
   docker exec surgical-pipeline sh -lc '
     timeout 6s gst-launch-1.0 gencamsrc serial=<SERIAL> pixel-format=ycbcr422_8 width=1280 height=720 \
       ! gvafpscounter interval=1 ! fakesink sync=false async=false'
   ```

3. **Reproduce the stall** — add `gvadetect` after direct `gencamsrc`; if it
   drops to ~11 FPS with the system idle, this is the issue.

4. **Apply the fix** — run the `basler_reader.py | fdsrc` command above; if it
   jumps to ~45 FPS, the decoupled reader is the solution for that host.

---

## Related

- Finalized (reference-host) pipeline: [basler-final-pipeline.md](basler-final-pipeline.md)
- Camera bridge: [pipeline/basler_reader.py](../../pipeline/basler_reader.py)
- Pipeline builder: [pipeline/pipeline_string.py](../../pipeline/pipeline_string.py)
- Control-plane launcher: [pipeline/launcher.py](../../pipeline/launcher.py)
