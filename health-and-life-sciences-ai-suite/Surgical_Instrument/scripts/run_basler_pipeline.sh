#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# BASLER LIVE PIPELINE  -  polyp detection, with RECORD/MEASURE toggle
# ============================================================================
# One script, three modes (mirrors the reference example's use_filesink branch):
#
#   RECORD=0 (default) : ... ! gvawatermark ! gvafpscounter ! fakesink
#                        + per-element latency trace -> critical-path summary
#   RECORD=1           : ... ! gvawatermark ! (download) ! jpegenc ! avimux
#                        ! filesink  -> saves an annotated .avi you can play back
#   DISPLAY_VIEW=1     : ... ! gvawatermark ! (download) ! autovideosink
#                        -> live window with detection boxes (needs X11 / RDP GUI)
#
# NOTE on the source: your DLStreamer 2026.1 image does NOT ship `gencamsrc`
# or `pylonsrc` (verified), so we cannot use the reference `gencamsrc ...`
# line. Instead we bridge the camera with pypylon (basler_reader.py) into
# `fdsrc`, then run the GPU-optimized path (vapostproc -> VAMemory/NV12 ->
# va-surface-sharing -> gvadetect device=GPU). This is the same detection,
# just far faster than the reference's CPU (bayer2rgb + videoconvert +
# device=CPU) path.
#
# Usage:
#   bash run_basler_pipeline.sh              # measure latency (fakesink)
#   RECORD=1 bash run_basler_pipeline.sh     # record annotated /videos/basler_output.avi
#   DISPLAY_VIEW=1 bash run_basler_pipeline.sh    # live window (run from RDP/desktop GUI)
#   SERIAL=40067928 FRAMES=1200 NIREQ=1 RECORD=1 bash run_basler_pipeline.sh
# ============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/logs/latency"
VID_DIR="${ROOT_DIR}/videos"
LOG_FILE="${LOG_DIR}/basler.log"
TXT_FILE="${LOG_DIR}/basler.summary.txt"
IMAGE="${IMAGE:-surgical-pipeline:dev}"

W="${W:-1920}"
H="${H:-1080}"
FPS="${FPS:-60}"
FRAMES="${FRAMES:-3000}"
NIREQ="${NIREQ:-1}"
SERIAL="${SERIAL:-}"                 # empty = first detected camera
RECORD="${RECORD:-0}"               # 1 = save annotated .avi instead of fakesink
DISPLAY_VIEW="${DISPLAY_VIEW:-0}"    # 1 = live autovideosink window (needs X11)
# LEAKY=1 -> queues drop the oldest frame when full (newest-frame-wins). This is
# the RIGHT choice for a LIVE feed: bounds latency by dropping stale frames
# instead of backing up behind a slow sink (e.g. RDP display). Off for pure
# throughput/measurement (every frame processed).
LEAKY="${LEAKY:-0}"
if [[ "${LEAKY}" == "1" ]]; then
  # newest-frame-wins: cap at 1 buffer AND ~1 frame of time (16 ms @ 60 fps).
  QUEUE="queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream"
else
  QUEUE="queue max-size-buffers=2 max-size-bytes=0 max-size-time=0"
fi
OUT_AVI="${OUT_AVI:-/videos/basler_output.avi}"
BLOCKSIZE=$(( W * H * 2 ))           # UYVY = 2 bytes/px

mkdir -p "${LOG_DIR}" "${VID_DIR}"
cd "${ROOT_DIR}"

RENDER_GID="$(getent group render | cut -d: -f3 || true)"
VIDEO_GID="$(getent group video  | cut -d: -f3 || true)"

GROUP_ARGS=()
if [[ -n "${RENDER_GID}" ]]; then GROUP_ARGS+=(--group-add "${RENDER_GID}"); fi
if [[ -n "${VIDEO_GID}" ]]; then GROUP_ARGS+=(--group-add "${VIDEO_GID}"); fi

# Choose the tail of the pipeline based on RECORD / DISPLAY_VIEW.
DISPLAY_ARGS=()
if [[ "${RECORD}" == "1" ]]; then
  # Download VAMemory -> system, encode JPEG, mux to AVI, write to file.
  SINK_TAIL="gvawatermark ! gvafpscounter interval=1 ! \
    vapostproc ! \"video/x-raw\" ! videoconvert ! \
    jpegenc ! avimux ! filesink location=${OUT_AVI}"
  MODE_DESC="RECORD -> ${OUT_AVI}"
  VID_MOUNT=(-v "${VID_DIR}:/videos:rw")
elif [[ "${DISPLAY_VIEW}" == "1" ]]; then
  # Live window. Download VAMemory -> system, then a video sink. Needs X11.
  if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY is empty. Run DISPLAY_VIEW=1 from the desktop / RDP GUI terminal."
    exit 1
  fi
  xhost +local:docker >/dev/null 2>&1 || { echo "xhost failed for DISPLAY=${DISPLAY}"; exit 1; }
  # autovideosink picks xvimagesink/glimagesink, which FAIL over RDP (no Xv/GL).
  # Default to plain software ximagesink (RDP-safe). Override with VSINK=...
  VSINK="${VSINK:-ximagesink}"
  if [[ "${MINIMAL:-0}" == "1" ]]; then
    # Lean path: keep vapostproc (needed for the sink to negotiate a surface it
    # can display - a bare "gvawatermark ! sink" fails with not-negotiated),
    # but drop gvafpscounter and the explicit videoconvert download. vapostproc
    # lets a hardware/GL sink import the surface; add videoconvert back if the
    # chosen sink still refuses (software sinks like ximagesink need it).
    SINK_TAIL="gvawatermark ! vapostproc ! ${VSINK} sync=false"
    MODE_DESC="DISPLAY (minimal: gvawatermark ! vapostproc ! ${VSINK})"
  else
    # Full path: download VAMemory -> system before the sink (needed for
    # software X sinks). Harmless (~0 ms) with a hardware sink.
    SINK_TAIL="gvawatermark ! gvafpscounter interval=1 ! \
      vapostproc ! \"video/x-raw\" ! videoconvert ! \
      ${VSINK} sync=false"
    MODE_DESC="DISPLAY (live ${VSINK} window)"
  fi
  VID_MOUNT=()
  DISPLAY_ARGS=(-e DISPLAY="${DISPLAY}" -e XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}" -v /tmp/.X11-unix:/tmp/.X11-unix:rw)
else
  SINK_TAIL="gvawatermark ! gvafpscounter interval=1 ! \
    fakesink sync=false async=false"
  MODE_DESC="MEASURE (fakesink + latency trace)"
  VID_MOUNT=()
fi

CMD="python3 /opt/basler_reader.py ${SERIAL} --geometry ${W}x${H}@${FPS} --pixel-format uyvy \
  | gst-launch-1.0 \
    fdsrc fd=0 blocksize=${BLOCKSIZE} do-timestamp=true ! \
    rawvideoparse format=yuy2 width=${W} height=${H} framerate=${FPS}/1 ! \
    vapostproc ! \"video/x-raw(memory:VAMemory),format=NV12\" ! \
    identity eos-after=${FRAMES} ! \
    ${QUEUE} ! \
    gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml device=GPU threshold=0.5 \
      pre-process-backend=va-surface-sharing nireq=${NIREQ} ie-config=PERFORMANCE_HINT=LATENCY ! \
    ${QUEUE} ! \
    ${SINK_TAIL}"

echo "============================================================"
echo "MODE:    ${MODE_DESC}"
echo "IMAGE:   ${IMAGE}"
echo "CAMERA:  serial='${SERIAL:-<first>}'  ${W}x${H}@${FPS}  nireq=${NIREQ}  leaky=${LEAKY}"
echo "FRAMES:  ${FRAMES}"
echo "============================================================"
echo "${CMD}"
echo "============================================================"

docker run --rm --entrypoint bash --net=host \
  -e 'GST_TRACERS=latency(flags=pipeline+element)' \
  -e GST_DEBUG=GST_TRACER:7 \
  -e GST_DEBUG_NO_COLOR=1 \
  "${DISPLAY_ARGS[@]}" \
  -v /dev/bus/usb:/dev/bus/usb \
  --device-cgroup-rule='c 189:* rmw' \
  -v "${ROOT_DIR}/models:/models:ro" \
  "${VID_MOUNT[@]}" \
  --device /dev/dri:/dev/dri \
  "${GROUP_ARGS[@]}" \
  "${IMAGE}" -lc "${CMD}" \
  2> >(tee "${LOG_FILE}" >&2)

if [[ "${RECORD}" == "1" ]]; then
  echo
  echo "Saved annotated video:  ${VID_DIR}/$(basename "${OUT_AVI}")"
  ls -lh "${VID_DIR}/$(basename "${OUT_AVI}")" 2>/dev/null || true
  exit 0
fi

# MEASURE and DISPLAY both parse the trace. In DISPLAY mode the sink IS the real
# display, so the whole-pipeline e2e is the closest camera-to-screen proxy we
# can measure (fdsrc -> display). In MEASURE mode the sink is fakesink, so e2e
# is pipeline-only.
if [[ "${DISPLAY_VIEW}" == "1" ]]; then
  E2E_LABEL="CAMERA-TO-SCREEN (fdsrc->display)"
else
  E2E_LABEL="E2E PIPELINE (fdsrc->fakesink)"
fi

echo
echo "===== LIVE CAMERA LATENCY  [leaky=${LEAKY}] ====="
python3 - "${LOG_FILE}" "${TXT_FILE}" "${E2E_LABEL}" <<'PY'
import re, sys, statistics

log, txt_out = sys.argv[1], sys.argv[2]
e2e_label = sys.argv[3] if len(sys.argv) > 3 else "E2E PIPELINE (fdsrc->sink)"
COMPUTE_PREFIXES = ("gvadetect", "gvawatermark", "gvafpscounter")
elem_re = re.compile(r"\selement-latency,.*element=\(string\)([^,]+),.*time=\(guint64\)(\d+)")
pipe_re = re.compile(r"\s(?<!element-)latency,.*time=\(guint64\)(\d+)")

per_elem = {}
e2e = []
with open(log, errors="ignore") as f:
    for line in f:
        m = elem_re.search(line)
        if m:
            ms = int(m.group(2)) / 1e6
            if ms <= 60_000.0:
                per_elem.setdefault(m.group(1), []).append(ms)
            continue
        p = pipe_re.search(line)
        if p:
            ms = int(p.group(1)) / 1e6
            if ms <= 60_000.0:
                e2e.append(ms)

if not per_elem and not e2e:
    sys.exit("No latency records found (camera may not have started).")

def stats(vals):
    v = sorted(vals)
    return (statistics.mean(v), v[len(v)//2], v[min(len(v)-1, int(0.99*len(v)+0.5))])

lines = []
lines.append(f"{'element':<20} {'samples':>8} {'mean_ms':>9} {'p99_ms':>8}")
lines.append("-" * 48)
critical = 0.0
for name in sorted(per_elem):
    mean, _, p99 = stats(per_elem[name])
    on_path = name.startswith(COMPUTE_PREFIXES)
    lines.append(f"{name:<20} {len(per_elem[name]):>8} {mean:>9.3f} {p99:>8.3f}{' *' if on_path else ''}")
    if on_path:
        critical += mean
lines.append("-" * 48)
lines.append(f"{'compute critical path (gva* sum)':<38} {critical:>9.3f} ms")
if e2e:
    mean, p50, p99 = stats(e2e)
    lines.append(f"{e2e_label + ' mean':<38} {mean:>9.3f} ms")
    lines.append(f"{e2e_label + ' p50/p99':<38} {p50:>7.2f} / {p99:.2f} ms")

out = "\n".join(lines) + "\n"
print(out, end="")
open(txt_out, "w").write(out)
PY

echo "Saved:"
echo "  ${LOG_FILE}"
echo "  ${TXT_FILE}"
