#!/usr/bin/env bash
# Convert the UrbanLoco ground truth to TUM format (if not already done),
# then compute RMSE between it and the trajectory produced by run_ulhk.sh
# via evo_ape, printing the documented baselines (Point-LIO and FAST-LIO2
# papers) alongside it.
#
# Usage: ./evaluate_rmse.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SEQ="${ULHK_SEQUENCE}"
EST_TUM="${RESULTS_DIR}/${SEQ}_est_tum.txt"
GT_TUM="${RESULTS_DIR}/${SEQ}_gt_tum.txt"

[[ -f "${EST_TUM}" ]] || { echo "Missing ${EST_TUM}; run ./run_ulhk.sh first." >&2; exit 1; }

if [[ ! -f "${GT_TUM}" ]]; then
  [[ -d "${BAG_DIR}" ]] || { echo "Missing bag at ${BAG_DIR}; run ./convert_ulhk_to_bag.sh first." >&2; exit 1; }
  mkdir -p "${RESULTS_DIR}"
  python3 "${SCRIPT_DIR}/extract_ulhk_gt.py" --bag-dir "${BAG_DIR}" --topic "${ULHK_GT_TOPIC}" --out "${GT_TUM}"
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
echo "    (baseline: Point-LIO paper, He et al. 2023, Advanced Intelligent Systems,"
echo "    DOI 10.1002/aisy.202200459, Table 5; FAST-LIO2's own paper, Xu et al. 2022,"
echo "    IEEE T-RO, Table IV, reports 2.57 m on this same sequence for context only)"

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
        printf "==> PASS: measured RMSE %.3f m is within +%s%% of baseline (<= %.3f m)\n", measured, tol, hi
        exit 0
      } else {
        printf "==> FAIL: measured RMSE %.3f m exceeds +%s%% of baseline (> %.3f m)\n", measured, tol, hi
        exit 1
      }
    }'
fi
