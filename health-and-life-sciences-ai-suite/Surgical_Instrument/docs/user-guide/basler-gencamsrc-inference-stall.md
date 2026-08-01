# Basler `gencamsrc` + `gvadetect` Inference Stall — Problem & Solution

## Summary

On the client host, the direct `gencamsrc` live pipeline collapses to
**~11–13 FPS** the moment `gvadetect` runs inference **on the GPU**, while the
CPU and GPU sit **mostly idle**. The camera alone is fast (~82 FPS), inference
alone is fast (~160 FPS on `videotestsrc`), and inference on the **CPU** with
the same camera is fast (~37 FPS) — only **`gencamsrc` + GPU inference in the
same process** stalls.

The root cause is an **in-process interaction between pylon (`gencamsrc`) and
the OpenVINO GPU runtime** on this specific host stack (Intel Arrow Lake-P
iGPU with **outdated GuC scheduler firmware**). Two fixes:

1. **Host fix (preferred):** update the client's GPU firmware/driver stack to
   match the working reference host — in particular the **GuC firmware**
   (`linux-firmware`), which the kernel itself reports as outdated.
2. **Application fix (host-independent):** **decouple camera acquisition** via
   `basler_reader.py | fdsrc`, which moves pylon into a separate process and
   sidesteps the contention (**~11 → ~45 FPS**).

- Affected camera in this investigation: **Basler daA1920-160uc** (dart, USB3),
  serial `40715749`.
- Client host: Intel **Arrow Lake-P** iGPU (`i915`), kernel `7.0.0-28-generic`.
- Working reference host: Intel **Arrow Lake-U** iGPU (`i915`), kernel
  `6.17.0-22-generic` — same pipeline runs at 120+ FPS.

---

## Problem

### Symptom

```text
FpsCounter(average 3.69sec): total=13.00 fps, number-streams=1, per-stream=13.00 fps
```

- Reported FPS is stuck at ~11–13.
- CPU **and** GPU are **underutilized** — it is not compute-bound, it is
  **blocking** (~77 ms per frame with idle silicon).
- Happens on the same git branch that runs at 120+ FPS on the reference host.

### What we measured (isolation tests, on the client machine)

Grouped by what each stage isolates. `→ fakesink` rows have **no inference**;
`→ gvadetect` rows add inference.

**Source & VA path (no inference):**

| Pipeline | FPS | Notes |
| --- | ---: | --- |
| `gencamsrc → fakesink` | ~82 | Camera acquisition is healthy |
| `gencamsrc → vapostproc → system NV12 → fakesink` | ~82 | VA convert to system memory is fine |
| `gencamsrc → vapostproc → VAMemory NV12 → fakesink` | ~10 | VAMemory export stalls (without normalize) |
| `gencamsrc → videoconvert(passthrough) → vapostproc → VAMemory → fakesink` | ~83 | Normalize fixes the VAMemory export |
| `gencamsrc → vapostproc → DMABuf → fakesink` | — | **Errors**: `DMABuf caps negotiated without mandatory VideoMeta` (not viable) |

**Inference alone (no camera):**

| Pipeline | FPS | Notes |
| --- | ---: | --- |
| `videotestsrc → gvadetect` (GPU, customer) | ~160 | GPU inference alone is fast |
| `videotestsrc (is-live=true) → vapostproc → VAMemory → gvadetect` (GPU) | ~82 | Live source + GPU inference is fine |

**Camera + GPU inference (the stall) — every variant tried:**

| Pipeline | FPS | Notes |
| --- | ---: | --- |
| **`gencamsrc → vapostproc → VAMemory → gvadetect` (va-surface-sharing)** | **~11** | Stalls |
| `gencamsrc → normalize → vapostproc → VAMemory → gvadetect` (va-surface-sharing) | ~11 | Normalize (that fixed `→ fakesink`) does **not** help inference |
| **`gencamsrc → videoconvert → gvadetect` (opencv, no VA)** | **~11** | Stalls — not VA, not backend |
| `gencamsrc → videoconvert(system NV12) → gvadetect` (va-surface-sharing) | — | **Errors**: va-surface-sharing requires VA memory, not system memory |
| `gencamsrc → vapostproc → system NV12 → vapostproc → VAMemory → gvadetect` | ~9 | Full GPU copy in between — still stalls |
| `gencamsrc → vapostproc → VAMemory → gvadetect` (`pre-process-backend=va`) | ~13 | Still stalls |
| `gencamsrc → … → gvadetect` + `taskset -c 0-7 chrt -f 80` | ~13 | CPU pinning / RT priority does **not** help |
| `gencamsrc → … → gvadetect` + `GPU_QUEUE_THROTTLE=LOW` | ~8 | No software lever helps |

**What actually works:**

| Pipeline | FPS | Notes |
| --- | ---: | --- |
| **`gencamsrc → videoconvert → gvadetect` (`device=CPU`)** | **~37** | **CPU inference does NOT stall** |
| **`basler_reader.py \| fdsrc → … → gvadetect` (GPU) @60** | **~45** | **Decoupled reader removes the stall** |
| `basler_reader.py \| fdsrc → … → gvadetect` (GPU) @120 | ~43 | Same as @60 → reader (Python) is now the ceiling, not inference |

### Root cause

The stall is triggered **only** when **OpenVINO GPU inference runs in the same
process as pylon (`gencamsrc`)**. The tests above rule out every other
candidate:

- **Not the camera** — raw capture is 82 FPS.
- **Not the preprocessing backend** — `va-surface-sharing`, `opencv`, and `va`
  all stall.
- **Not VA / VAMemory** — the `opencv` path (no `vapostproc`) also stalls; a
  full GPU download-and-reupload in between still stalls (~9 FPS).
- **Not buffer memory / lifetime** — copying the frame into fresh
  GPU-produced system memory before inference does not help.
- **Not source liveness** — `videotestsrc is-live=true` + GPU inference = 82 FPS.
- **Not CPU scheduling** — `taskset` + `chrt -f 80` across all cores = 13 FPS.
- **`device=CPU` does NOT stall (~37 FPS)** — this is the decisive test: same
  `gencamsrc`, only the inference device changed. The problem is specific to
  the **GPU** compute path.

So the pylon USB/GenTL acquisition thread is **starved/serialized by the
OpenVINO GPU runtime** when both run in one process, blocking ~77 ms/frame
with the hardware idle. This is **host-specific** — the reference host does
not show it — which points to a **driver / GPU-firmware level** issue on the
client's stack (see machine comparison below). The decoupled reader works
because it isolates pylon in a **separate process** from the GPU runtime.

---

## Machine comparison (working vs client)

Both are Intel **Arrow Lake** iGPUs using the **`i915`** kernel driver, so the
DRM driver is not the difference. The deltas are the kernel, the host media
driver, and — most tellingly — the **GuC firmware**:

| | Working host (120+ FPS) | Client host (~11 FPS) |
| --- | --- | --- |
| GPU | Arrow Lake-**U** `Intel Graphics`, `i915` | Arrow Lake-**P** `Arc Graphics`, `i915` |
| Kernel | `6.17.0-22-generic` | `7.0.0-28-generic` |
| **GuC firmware** | recommended `70.53.0` | **`70.36.0` — outdated** ⚠️ |
| Host media VA driver | `intel-media-va-driver-non-free` `26.1.4` | `intel-media-va-driver` `24.1.0` (stock, upgradable to `26.2.2`) |
| OpenCL ICD | `26.05.37020.3` | `26.22.38646.6` |

The client's own kernel log flags the firmware gap directly:

```text
i915 GT0: GuC firmware i915/mtl_guc_70.bin (70.53.0) is recommended,
          but only i915/mtl_guc_70.bin (70.36.0) was found
          Consider updating your linux-firmware pkg
```

**GuC is the GPU's workload-scheduling firmware.** A stale GuC on Arrow Lake
is a strong candidate for GPU-submission stalls that starve the in-process
pylon acquisition thread — exactly the observed symptom.

---

## Solution

There are two independent fixes. Prefer the host fix if the client can update
their GPU stack; otherwise ship the application fix, which is
host-independent.

### Fix A (preferred) — update the client's GPU firmware / driver stack

The client's kernel reports outdated GuC scheduler firmware, and the host
media driver is older than the working reference host. Align them:

```bash
# on the client HOST (not the container)

# 1) PRIME SUSPECT — update GPU firmware (GuC 70.36.0 -> recommended 70.53.0)
sudo apt update
sudo apt install --only-upgrade linux-firmware
sudo reboot
# after reboot, confirm the newer GuC actually loaded:
sudo dmesg | grep -iE "GuC firmware .*version"

# 2) match the working host's media driver (non-free 26.1.4)
sudo apt install intel-media-va-driver-non-free
```

If firmware still lags after the package update, pull the blob directly from
[linux-firmware](https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/tree/i915),
copy `i915/mtl_guc_70.bin`, `sudo update-initramfs -u`, and reboot.

Then re-run the direct `gencamsrc + GPU` test (see Diagnose step 3). If it
jumps from ~11 toward full FPS, the stale firmware/driver was the root cause
and no application change is needed.

> The container bundles its own `iHD` `26.1.4` for VA, but the OpenVINO GPU
> plugin uses the **host** Level Zero / compute runtime — so the host update
> (and reboot) is what matters.

### Fix B (host-independent) — decouple acquisition with `basler_reader.py | fdsrc`

Instead of `gencamsrc` feeding the pipeline directly, run the existing
[`pipeline/basler_reader.py`](../../pipeline/basler_reader.py) bridge. It
grabs frames with pypylon in a **separate process** and writes raw bytes to
stdout; `fdsrc` then feeds the pipeline. Moving pylon out of the inference
process removes the in-process GPU contention entirely.

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
| Direct `gencamsrc → gvadetect` (GPU) | ~11 |
| Direct `gencamsrc → gvadetect` (**CPU**) | ~37 |
| `basler_reader.py \| fdsrc → gvadetect` (GPU) | ~45 |

The stall is eliminated with the reader. `gvadetect` is no longer the
bottleneck.

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

3. **Reproduce the stall** — add `gvadetect device=GPU` after direct
   `gencamsrc`; if it drops to ~11 FPS with CPU **and** GPU idle, this is the
   issue:
   ```bash
   docker exec surgical-pipeline sh -lc '
     timeout 20s gst-launch-1.0 \
       gencamsrc serial=<SERIAL> pixel-format=ycbcr422_8 width=1280 height=720 \
       ! vapostproc ! "video/x-raw(memory:VAMemory),format=NV12" \
       ! queue max-size-buffers=2 leaky=downstream \
       ! gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml \
           device=GPU pre-process-backend=va-surface-sharing nireq=1 batch-size=1 \
       ! gvafpscounter interval=1 ! fakesink sync=false async=false'
   ```

4. **Confirm it is GPU-specific** — repeat with `device=CPU`
   (`pre-process-backend=opencv`, `video/x-raw,format=BGRx`). If CPU runs
   ~37 FPS while GPU is ~11, the stall is the in-process GPU/pylon contention.

5. **Compare the GPU stack vs a working host** — the key deltas are kernel,
   GuC firmware, and media driver:
   ```bash
   # on the HOST
   uname -r
   sudo lspci -k | grep -A3 -iE "VGA|Display"          # confirm i915 vs xe
   sudo dmesg | grep -iE "GuC firmware"                # look for "outdated"/version
   apt list --installed 2>/dev/null | grep -iE "intel-media|intel-opencl|level-zero"
   ```

6. **Apply a fix** — either update the host GPU stack (Fix A) and re-run
   step 3, or run the `basler_reader.py | fdsrc` command (Fix B); if the
   reader jumps to ~45 FPS, it is the solution for that host.

---

## Related

- Finalized (reference-host) pipeline: [basler-final-pipeline.md](basler-final-pipeline.md)
- Camera bridge: [pipeline/basler_reader.py](../../pipeline/basler_reader.py)
- Pipeline builder: [pipeline/pipeline_string.py](../../pipeline/pipeline_string.py)
- Control-plane launcher: [pipeline/launcher.py](../../pipeline/launcher.py)
