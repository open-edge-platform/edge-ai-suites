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
iGPU, kernel `7.0.0-28-generic`). **Update:** updating the GuC scheduler
firmware to `70.53.0` (matching the working host) did **not** resolve it —
still ~8–9 FPS — so the firmware version is not the cause. The reliable fix
is therefore the application-level one:

1. **Application fix (shipping solution, host-independent):** **decouple
   camera acquisition** via `basler_reader.py | fdsrc`, which moves pylon into
   a separate process and sidesteps the contention (**~11 → ~45 FPS**).
2. **Host fix (inconclusive):** aligning the client's GPU firmware/driver
   stack to the working host — GuC firmware update tried, did not help; media
   driver / kernel alignment still untested as a full set.

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
not show it. Matching the reference host to the client's full software stack
(kernel, driver, firmware) did **not** reproduce it (see below), so the
trigger is **hardware** — specifically the **daA (dart) camera** interacting
with in-process GPU inference. The decoupled reader works because it isolates
pylon in a **separate process** from the GPU runtime.

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
was the strongest initial suspect — **however, updating it to `70.53.0`
(matching the working host) did NOT resolve the stall (still ~8–9 FPS).** So
the GuC firmware version is ruled out.

### Software fully ruled out — matched-host reproduction

To eliminate every software variable, the **working host was upgraded to the
client's exact kernel** (`7.0.0-28-generic`) and its GPU stack was compared
component-by-component. After matching, both machines are identical on every
software layer that OpenVINO-GPU touches — yet only the client stalls:

| Component | Working host | Client host | Match |
| --- | --- | --- | --- |
| Kernel | `7.0.0-28-generic` (upgraded to match) | `7.0.0-28-generic` | ✅ |
| DRM driver | `i915` | `i915` | ✅ |
| Level Zero GPU `.so` | `1.14.37020` | `1.14.37020` | ✅ |
| GuC firmware | `70.53.0` | `70.53.0` | ✅ |
| **`gencamsrc` + GPU inference** | **~140 FPS** | **~11 FPS** | ❌ |

With kernel, DRM driver, Level Zero GPU driver, and firmware all identical and
the working host still hitting ~140 FPS, **software is eliminated.** The only
remaining differences are **hardware**:

1. **GPU SKU** — Arrow Lake-**U** (works) vs Arrow Lake-**P** (stalls).
2. **Camera model** — acA (ace, works) vs **daA1920-160uc (dart)** (stalls).

The decisive clue is on the client itself: **GPU inference alone**
(`videotestsrc`) = ~160 FPS and **camera alone** = ~82 FPS, but the two
**together** = ~11 FPS. The one factor present in every broken case and absent
from every working case is the **dart (daA) camera**. Dart cameras use a
different USB/pylon acquisition path than ace (acA) cameras, and that path
appears to contend with the in-process OpenVINO GPU runtime on the client.

**Prime suspect: the daA1920-160uc dart camera's pylon/USB acquisition
contending with in-process GPU inference.** Decisive confirmation = swap the
dart camera onto the working (Arrow Lake-U) host; if it stalls there too, the
camera is confirmed and the issue reproduces locally. Either way, the
**decoupled reader (which moves pylon out of the inference process) is the
definitive fix.**

---

## Camera comparison (dart vs ace)

Captured with `pypylon` (see `basler_probe.py`). The client's **daA (dart)**
vs the working host's **acA (ace)**:

| Property | Client — daA1920-160uc (dart) | Host — acA1920-150uc (ace) |
| --- | --- | --- |
| Transport layer | `BaslerUsb` (USB3) | `BaslerUsb` (USB3) |
| Sensor / firmware | `imx392c`, `v=2.6.0` | `V1.4-4` |
| `DeviceLinkThroughput` | **160,000,000** (160 MB/s) | **300,000,000** (300 MB/s) |
| `DeviceLinkCurrentThroughput` | `<n/a>` (node absent) | `299,964,850` |
| Max resolution | 1936 × 1216 | 1984 × 1264 |
| `ResultingFrameRate` @1280×720 | **82.5 fps** | 162.8 fps |
| Frame-rate node | `AcquisitionFrameRate` (+`Enable`) | `AcquisitionFrameRate` (+`Enable`) |
| `AcquisitionFrameRateAbs` | absent (`LogicalErrorException`) | absent (`LogicalErrorException`) |
| Pixel formats | Mono8/12, RGB8, BGR8, **YCbCr422_8**, BayerRG8/12 | Mono8, BayerBG8/10, RGB8, BGR8, **YCbCr422_8** |

Two takeaways:

1. **Frame-rate node (reader fix):** *both* cameras expose
   `AcquisitionFrameRate` + `AcquisitionFrameRateEnable`, and **neither** has
   `AcquisitionFrameRateAbs` under the current pylon SDK. `basler_reader.py`
   hardcodes the `...Abs` node, so its frame-rate set fails on both — this is
   why the reader is capped at ~45 fps. Fix: set `AcquisitionFrameRateEnable=true`
   + `AcquisitionFrameRate`, with `...Abs` only as a legacy fallback.
2. **Throughput:** the dart is limited to **160 MB/s** vs the ace's 300 MB/s,
   and its `ResultingFrameRate` is 82.5 fps (matching the observed ~82 fps
   camera-only). This is a hardware/transport difference between the models,
   but it does **not** by itself explain the stall — the dart hits its full
   82 fps when the camera runs alone; the collapse to ~11 fps only appears
   once in-process GPU inference is added.

Full readouts:

```text
# ================= Client — daA1920-160uc (dart), serial 40715749 =================
=== Enumerated devices ===
  model=daA1920-160uc  serial=40715749  tl=BaslerUsb

=== Selected camera ===
  Model                : daA1920-160uc
  Serial               : 40715749
  Firmware             : p=du1b_imx392c/s=r/v=2.6.0/i=10405.6/h=232ba9e
  DeviceLinkSpeed Bps  : <n/a: LogicalErrorException>
  DeviceLinkThroughput : 160000000
  DeviceLinkCurrentThr : <n/a: LogicalErrorException>

=== Geometry ===
  Width               : 1280
  Height              : 720
  WidthMax            : 1936
  HeightMax           : 1216
  PixelFormat         : YCbCr422_8

=== Frame-rate nodes (which one this model uses) ===
  AcquisitionFrameRateEnable  : False
  AcquisitionFrameRate        : 100.0
  AcquisitionFrameRateAbs     : <n/a: LogicalErrorException>
  ResultingFrameRate          : 82.5218682950982
  ResultingFrameRateAbs       : <n/a: LogicalErrorException>

=== Exposure / gain ===
  ExposureAuto        : Off
  ExposureTime        : 5000.0
  ExposureTimeAbs     : <n/a: LogicalErrorException>
  GainAuto            : Off
  Gain                : 0.0

=== Available pixel formats ===
  Mono8, Mono12, Mono12p, RGB8, BGR8, YCbCr422_8, BayerRG8, BayerRG12, BayerRG12p


# ================= Host — acA1920-150uc (ace), serial 40067928 =================
=== Enumerated devices ===
  model=acA1920-150uc  serial=40067928  tl=BaslerUsb

=== Selected camera ===
  Model                : acA1920-150uc
  Serial               : 40067928
  Firmware             : 107262-14;U;acA1920_150uc;V1.4-4;1
  DeviceLinkSpeed Bps  : <n/a: LogicalErrorException>
  DeviceLinkThroughput : 300000000
  DeviceLinkCurrentThr : 299964850

=== Geometry ===
  Width               : 1280
  Height              : 720
  WidthMax            : 1984
  HeightMax           : 1264
  PixelFormat         : YCbCr422_8

=== Frame-rate nodes (which one this model uses) ===
  AcquisitionFrameRateEnable  : False
  AcquisitionFrameRate        : 222.22222222222223
  AcquisitionFrameRateAbs     : <n/a: LogicalErrorException>
  ResultingFrameRate          : 162.76041666666666
  ResultingFrameRateAbs       : <n/a: LogicalErrorException>

=== Exposure / gain ===
  ExposureAuto        : Off
  ExposureTime        : 5000.0
  ExposureTimeAbs     : <n/a: LogicalErrorException>
  GainAuto            : Off
  Gain                : 0.0

=== Available pixel formats ===
  Mono8, BayerBG8, BayerBG10, BayerBG10p, RGB8, BGR8, YCbCr422_8
```

---

## Solution

The **decoupled reader (Fix B)** is the shipping solution — it is
host-independent and proven. Fix A (host driver/firmware alignment) was
attempted (GuC firmware update) and did **not** resolve the stall, so it is
kept only as an in-progress investigation track.

### Fix A (attempted, inconclusive) — align the client's GPU firmware / driver stack

The client's kernel originally reported outdated GuC scheduler firmware, and
the host media driver is older than the working reference host. Alignment
steps:

```bash
# on the client HOST (not the container)

# 1) GuC firmware 70.36.0 -> 70.53.0  (DONE — confirmed loaded, but did NOT fix it)
sudo apt update
sudo apt install --only-upgrade linux-firmware
sudo reboot
sudo dmesg | grep -iE "GuC firmware .*version"   # now reports 70.53.0

# 2) still to try as a full set: media driver + Level Zero + kernel
sudo apt install intel-media-va-driver-non-free intel-level-zero-gpu level-zero libze1
```

> Result so far: **GuC firmware `70.53.0` did not change the ~8–9 FPS stall.**
> The container bundles its own `iHD` `26.1.4` for VA, but the OpenVINO GPU
> plugin uses the **host** Level Zero / compute runtime — so host media driver
> + Level Zero + kernel remain the only unverified variables.

### Fix B (shipping solution, host-independent) — decouple acquisition with `basler_reader.py | fdsrc`

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
