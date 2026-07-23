#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs/latency"
LOG_FILE="${LOG_DIR}/tuned_no_leaky.log"
TXT_FILE="${LOG_DIR}/tuned_no_leaky.summary.txt"
JSON_FILE="${LOG_DIR}/tuned_no_leaky.summary.json"
IMAGE="${IMAGE:-surgical-pipeline:dev}"

mkdir -p "${LOG_DIR}"
cd "${ROOT_DIR}"

RENDER_GID="$(getent group render | cut -d: -f3 || true)"
VIDEO_GID="$(getent group video  | cut -d: -f3 || true)"

GROUP_ARGS=()
if [[ -n "${RENDER_GID}" ]]; then GROUP_ARGS+=(--group-add "${RENDER_GID}"); fi
if [[ -n "${VIDEO_GID}" ]]; then GROUP_ARGS+=(--group-add "${VIDEO_GID}"); fi

PIPELINE='gst-launch-1.0 -v \
  filesrc location=/videos/polyp_test.mp4 ! qtdemux ! h264parse ! vah264dec ! \
  identity eos-after=3000 ! \
  queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 ! \
  gvadetect model=/models/yolo11n_polyp/best_openvino_model/best.xml device=GPU threshold=0.5 pre-process-backend=ie nireq=1 ! \
  queue max-size-buffers=1 max-size-bytes=0 max-size-time=0 ! \
  gvawatermark ! gvafpscounter interval=1 ! \
  fakesink sync=false async=false'

echo "============================================================"
echo "MODE: TUNED_NO_LEAKY"
echo "IMAGE: ${IMAGE}"
echo "LOG: ${LOG_FILE}"
echo "PIPELINE:"
echo "${PIPELINE}"
echo "============================================================"

docker run --rm --entrypoint bash --net=host \
  -e 'GST_TRACERS=latency(flags=pipeline)' \
  -e GST_DEBUG=GST_TRACER:7 \
  -e GST_DEBUG_NO_COLOR=1 \
  -v "${ROOT_DIR}/models:/models:ro" \
  -v "${ROOT_DIR}/videos:/videos:ro" \
  --device /dev/dri:/dev/dri \
  "${GROUP_ARGS[@]}" \
  "${IMAGE}" -lc "${PIPELINE}" \
  2> >(tee "${LOG_FILE}" >&2)

python3 "${ROOT_DIR}/scripts/parse_latency_log.py" "${LOG_FILE}" \
  --txt-out "${TXT_FILE}" \
  --json-out "${JSON_FILE}"

echo "Saved:"
echo "  ${LOG_FILE}"
echo "  ${TXT_FILE}"
echo "  ${JSON_FILE}"