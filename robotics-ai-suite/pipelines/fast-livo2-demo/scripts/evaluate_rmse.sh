#!/usr/bin/env bash
# Convert the fast_livo2 trajectory produced by run_ntu_viral.sh into
# the PRISM coordinate frame, convert the official ground truth to TUM
# format, and compute RMSE against it with evo_ape - printing the documented
# baseline from FAST-LIVO2/Log/result/ntu_viral/README.md alongside it.
#
# Usage: ./evaluate_rmse.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SEQ="${NTU_VIRAL_SEQUENCE}"
RESULT_FILE="${FASTLIVO2_SRC}/Log/result/${SEQ}.txt"
GT_CSV="${DATASET_DIR}/leica_pose_${SEQ}.csv"
EVAL_DIR="${FASTLIVO2_SRC}/Log/result/ntu_viral"
PRISM_FILE="${EVAL_DIR}/${SEQ}_prism_repro.txt"
GT_TUM_FILE="${EVAL_DIR}/${SEQ}_gt_repro.txt"

[[ -f "${RESULT_FILE}" ]] || { echo "Missing ${RESULT_FILE}; run ./run_ntu_viral.sh first." >&2; exit 1; }
[[ -f "${GT_CSV}" ]] || { echo "Missing ${GT_CSV}; run ./fetch_ntu_viral.sh first." >&2; exit 1; }

python3 - "${EVAL_DIR}" "${RESULT_FILE}" "${PRISM_FILE}" "${GT_CSV}" "${GT_TUM_FILE}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from evaluate_viral import convert_slam_to_prism, convert_leica_to_tum
convert_slam_to_prism(sys.argv[2], sys.argv[3])
convert_leica_to_tum(sys.argv[4], sys.argv[5])
PY

echo "==> Computing RMSE with evo_ape"
python3 -c "import evo" 2>/dev/null || pip install --user --break-system-packages evo
# `pip install --user` puts console scripts in ~/.local/bin, which isn't
# guaranteed to be on PATH (e.g. a non-interactive SSH session) - use it
# explicitly rather than relying on evo_ape already being on PATH.
EVO_OUTPUT="$(PATH="${HOME}/.local/bin:${PATH}" evo_ape tum "${GT_TUM_FILE}" "${PRISM_FILE}" -a)"
echo "${EVO_OUTPUT}"

# evo_ape's summary table reports rmse in meters; convert to cm to compare
# against expected_rmse_cm().
MEASURED_RMSE_M="$(echo "${EVO_OUTPUT}" | grep -i '^\s*rmse' | awk '{print $2}')"
MEASURED_RMSE_CM="$(awk -v m="${MEASURED_RMSE_M}" 'BEGIN { printf "%.2f", m * 100 }')"
BASELINE_RMSE_CM="$(expected_rmse_cm "${SEQ}")"

echo
echo "==> Sequence ${SEQ}: measured RMSE = ${MEASURED_RMSE_CM} cm, documented baseline = ${BASELINE_RMSE_CM} cm"
echo "    (baseline measured on hku-mars reference runs, see FAST-LIVO2/Log/result/ntu_viral/README.md)"

if [[ "${BASELINE_RMSE_CM}" == "unknown" ]]; then
  echo "==> No documented baseline for ${SEQ}; skipping pass/fail check."
else
  awk -v measured="${MEASURED_RMSE_CM}" -v baseline="${BASELINE_RMSE_CM}" -v tol="${RMSE_TOLERANCE_PCT}" '
    BEGIN {
      lo = baseline * (1 - tol / 100)
      hi = baseline * (1 + tol / 100)
      if (measured >= lo && measured <= hi) {
        printf "==> PASS: measured RMSE is within +/-%s%% of baseline (%.2f-%.2f cm)\n", tol, lo, hi
        exit 0
      } else {
        printf "==> FAIL: measured RMSE is outside +/-%s%% of baseline (%.2f-%.2f cm)\n", tol, lo, hi
        exit 1
      }
    }'
fi
