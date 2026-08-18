#!/usr/bin/env bash
# Convert the NCLT ground truth to TUM format (if not already done), then
# compute RMSE between it and the trajectory produced by run_nclt.sh via
# evo_ape, printing the documented baseline (FAST-LIO2 paper Table IV)
# alongside it.
#
# Usage: ./evaluate_rmse.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SEQ="${NCLT_SEQUENCE}"
EST_TUM="${RESULTS_DIR}/${SEQ}_est_tum.txt"
GT_TUM="${RESULTS_DIR}/${SEQ}_gt_tum.txt"

[[ -f "${EST_TUM}" ]] || { echo "Missing ${EST_TUM}; run ./run_nclt.sh first." >&2; exit 1; }

if [[ ! -f "${GT_TUM}" ]]; then
  GT_CSV="$(find "${DATASET_DIR}" -maxdepth 1 -name 'groundtruth_*.csv' | head -1)"
  [[ -n "${GT_CSV}" ]] || { echo "Missing groundtruth_*.csv under ${DATASET_DIR}; run ./fetch_nclt.sh first." >&2; exit 1; }
  mkdir -p "${RESULTS_DIR}"
  python3 "${SCRIPT_DIR}/extract_nclt_gt.py" --csv "${GT_CSV}" --out "${GT_TUM}"
fi

echo "==> Computing RMSE with evo_ape"
python3 -c "import evo" 2>/dev/null || pip install --user --break-system-packages evo
# `pip install --user` puts console scripts in ~/.local/bin, which isn't
# guaranteed to be on PATH (e.g. a non-interactive SSH session) - use it
# explicitly rather than relying on evo_ape already being on PATH.
EVO_OUTPUT="$(PATH="${HOME}/.local/bin:${PATH}" evo_ape tum "${GT_TUM}" "${EST_TUM}" -a)"
echo "${EVO_OUTPUT}"

MEASURED_RMSE_M="$(echo "${EVO_OUTPUT}" | grep -i '^\s*rmse' | awk '{print $2}')"
BASELINE_RMSE_M="$(expected_rmse_m "${SEQ}")"

echo
echo "==> Sequence ${SEQ}: measured RMSE = ${MEASURED_RMSE_M} m, documented baseline = ${BASELINE_RMSE_M} m"
echo "    (baseline: FAST-LIO2 paper, arXiv 2107.06829, Table IV - single-paper citation;"
echo "    Point-LIO's benchmark table does not cover any NCLT sequence)"

if [[ -n "${PLAY_START_OFFSET_S}${PLAY_DURATION_S}" ]]; then
  echo "==> Playback used a time slice (start_offset=${PLAY_START_OFFSET_S:-0}s" \
       "duration=${PLAY_DURATION_S:-full}s); the documented baseline is for the" \
       "full sequence, skipping pass/fail check."
elif [[ "${BASELINE_RMSE_M}" == "unknown" ]]; then
  echo "==> No documented baseline for ${SEQ}; skipping pass/fail check."
else
  # One-sided: this check exists to catch regressions, so a measured RMSE
  # at or below the baseline (however much lower) always passes - only a
  # measured RMSE worse than the baseline by more than the tolerance fails.
  awk -v measured="${MEASURED_RMSE_M}" -v baseline="${BASELINE_RMSE_M}" -v tol="${RMSE_TOLERANCE_PCT}" '
    BEGIN {
      hi = baseline * (1 + tol / 100)
      if (measured <= hi) {
        printf "==> PASS: measured RMSE %.2f m is within +%s%% of baseline (<= %.2f m)\n", measured, tol, hi
        exit 0
      } else {
        printf "==> FAIL: measured RMSE %.2f m exceeds +%s%% of baseline (> %.2f m)\n", measured, tol, hi
        exit 1
      }
    }'
fi
