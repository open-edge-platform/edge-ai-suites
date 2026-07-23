#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# BEST PIPELINE  -  Surgical Instrument polyp detection (GPU)
# ============================================================================
# This is the finalized, fastest *and* correctly-measured configuration.
#
# Winning data path (validated by A/B benchmarks):
#   vah264dec (GPU decode)
#     -> video/x-raw(memory:VAMemory)          keep frames on the GPU
#     -> gvadetect pre-process-backend=va-surface-sharing   ZERO-COPY preprocess
#                  ie-config=PERFORMANCE_HINT=LATENCY        latency-tuned request
#                  nireq=1                                    matches production default
#     -> gvawatermark -> gvafpscounter -> fakesink sync=false
#
#   identity sync=true  -> paces the file to real time (like a 60 fps camera),
#                          so no firehose queue-backlog inflates the numbers.
#   queues: max-size-buffers=2, NO leaky  -> every frame processed, no drops.
#
# Measurement: GST_TRACERS=latency(flags=element) records per-element src->sink
# time. We sum the mean latency of the COMPUTE elements (gvadetect + watermark +
# fpscounter) to get the true critical-path / camera-to-screen latency, and we
# EXCLUDE source/decode/queue/identity elements (those carry the read-ahead and
# pacing artifacts that pollute whole-pipeline latency).
# ============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/logs/latency"
LOG_FILE="${LOG_DIR}/most_optimized.log"
TXT_FILE="${LOG_DIR}/most_optimized.summary.txt"
IMAGE="${IMAGE:-surgical-pipeline:dev}"
FRAMES="${FRAMES:-3000}"
NIREQ="${NIREQ:-1}"
# Optional: SCALE_METHOD=fast enables VAAPI-based resize in preprocessing.
# Leave empty for the gvadetect default. Set via: SCALE_METHOD=fast bash run_latency.sh
SCALE_METHOD="${SCALE_METHOD:-}"
SCALE_OPT=""
if [[ -n "${SCALE_METHOD}" ]]; then SCALE_OPT="scale-method=${SCALE_METHOD} "; fi
# DISPLAY_VIEW=1 -> render to a live window (needs X11 / RDP GUI) instead of
# fakesink. LEAKY=1 -> newest-frame-wins queues (bounds latency under a slow
# sink; recommended with DISPLAY_VIEW). VSINK overrides the display sink
# (ximagesink is RDP-safe; use glimagesink on a real monitor).
DISPLAY_VIEW="${DISPLAY_VIEW:-0}"
LEAKY="${LEAKY:-0}"
VSINK="${VSINK:-ximagesink}"
if [[ "${LEAKY}" == "1" ]]; then
  QUEUE="queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream"
else
  QUEUE="queue max-size-buffers=2 max-size-bytes=0 max-size-time=0"
fi

mkdir -p "${LOG_DIR}"
cd "${ROOT_DIR}"

RENDER_GID="$(getent group render | cut -d: -f3 || true)"
VIDEO_GID="$(getent group video  | cut -d: -f3 || true)"

GROUP_ARGS=()
if [[ -n "${RENDER_GID}" ]]; then GROUP_ARGS+=(--group-add "${RENDER_GID}"); fi
if [[ -n "${VIDEO_GID}" ]]; then GROUP_ARGS+=(--group-add "${VIDEO_GID}"); fi

# Sink tail: live display window (DISPLAY_VIEW=1) or fakesink (measure).
DISPLAY_ARGS=()
if [[ "${DISPLAY_VIEW}" == "1" ]]; then
  if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY is empty. Run DISPLAY_VIEW=1 from the desktop / RDP GUI terminal."
    exit 1
  fi
  xhost +local:docker >/dev/null 2>&1 || { echo "xhost failed for DISPLAY=${DISPLAY}"; exit 1; }
  # Download VAMemory -> system before an X sink (X sinks can't take VA surfaces).
  SINK_TAIL="gvawatermark ! gvafpscounter interval=1 ! vapostproc ! \"video/x-raw\" ! videoconvert ! ${VSINK} sync=false"
  MODE_DESC="DISPLAY (live ${VSINK} window)"
  DISPLAY_ARGS=(-e DISPLAY="${DISPLAY}" -e XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}" -v /tmp/.X11-unix:/tmp/.X11-unix:rw)
else
  SINK_TAIL="gvawatermark ! gvafpscounter interval=1 ! fakesink sync=false async=false"
  MODE_DESC="MEASURE (fakesink)"
fi

PIPELINE="gst-launch-1.0  \
  filesrc location=/videos/polyp_test.mp4 ! qtdemux ! h264parse ! vah264dec ! \
  \"video/x-raw(memory:VAMemory)\" ! \
  identity sync=true eos-after=${FRAMES} ! \
  ${QUEUE} ! \
  gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml device=GPU threshold=0.5 \
    pre-process-backend=va-surface-sharing ${SCALE_OPT} nireq=${NIREQ} ie-config=PERFORMANCE_HINT=LATENCY ! \
  ${QUEUE} ! \
  ${SINK_TAIL}"

echo "============================================================"
echo "MODE:   ${MODE_DESC}  [leaky=${LEAKY}]"
echo "IMAGE:  ${IMAGE}"
echo "FRAMES: ${FRAMES}"
echo "NIREQ:  ${NIREQ}"
echo "LOG:    ${LOG_FILE}"
echo "============================================================"
echo "${PIPELINE}"
echo "============================================================"

docker run --rm --entrypoint bash --net=host \
  -e 'GST_TRACERS=latency(flags=pipeline+element)' \
  -e GST_DEBUG=GST_TRACER:7 \
  -e GST_DEBUG_NO_COLOR=1 \
  "${DISPLAY_ARGS[@]}" \
  -v "${ROOT_DIR}/models:/models:ro" \
  -v "${ROOT_DIR}/videos:/videos:ro" \
  --device /dev/dri:/dev/dri \
  "${GROUP_ARGS[@]}" \
  "${IMAGE}" -lc "${PIPELINE}" \
  2> >(tee "${LOG_FILE}" >&2)

echo
echo "===== CRITICAL-PATH (camera-to-screen) LATENCY ====="
python3 - "${LOG_FILE}" "${TXT_FILE}" <<'PY'
import re, sys, statistics

log, txt_out = sys.argv[1], sys.argv[2]

# Compute elements on the critical path (inference + post). Source/decode/queue/
# identity are excluded: they carry read-ahead + pacing, not compute cost.
COMPUTE_PREFIXES = ("gvadetect", "gvawatermark", "gvafpscounter")

rec = re.compile(r"\selement-latency,.*element=\(string\)([^,]+),.*time=\(guint64\)(\d+)")
# Drop guint64 underflow wraps (negative latency -> ~2^64). Any real element
# latency is well under 60 s.
MAX_MS = 60_000.0
per_elem = {}
with open(log, errors="ignore") as f:
    for line in f:
        m = rec.search(line)
        if not m:
            continue
        name, t_ns = m.group(1), int(m.group(2))
        ms = t_ns / 1e6
        if ms > MAX_MS:
            continue
        per_elem.setdefault(name, []).append(ms)

if not per_elem:
    sys.exit("No element-latency records found (need GST_TRACERS='latency(flags=element)').")

lines = []
critical = 0.0
lines.append(f"{'element':<20} {'samples':>8} {'mean_ms':>9} {'p99_ms':>8}")
lines.append("-" * 48)
for name in sorted(per_elem):
    vals = sorted(per_elem[name])
    mean = statistics.mean(vals)
    p99 = vals[min(len(vals) - 1, int(0.99 * len(vals) + 0.5))]
    on_path = name.startswith(COMPUTE_PREFIXES)
    mark = " *" if on_path else "  "
    lines.append(f"{name:<20} {len(vals):>8} {mean:>9.3f} {p99:>8.3f}{mark}")
    if on_path:
        critical += mean

lines.append("-" * 48)
lines.append(f"{'CRITICAL PATH (sum of *)':<38} {critical:>9.3f} ms")
lines.append("(* = compute elements summed for camera-to-screen latency;")
lines.append(" source/decode/queue/identity excluded as pacing artifacts)")

out = "\n".join(lines) + "\n"
print(out, end="")
open(txt_out, "w").write(out)
PY

echo "Saved:"
echo "  ${LOG_FILE}"
echo "  ${TXT_FILE}"
