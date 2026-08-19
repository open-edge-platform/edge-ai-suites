#!/usr/bin/env bash
# Download the NCLT sequence configured in env.sh. Unlike the datasets used
# by other RAI-suite SLAM demos, NCLT is hosted directly (via S3, linked
# from http://robots.engin.umich.edu/nclt/) with stable, ungated HTTPS
# URLs - this is a plain `wget`, no manual download step or access request
# needed. URLs below were confirmed live (HTTP 200) against the actual
# nclt.perl.engin.umich.edu S3 bucket, not the /nclt/data/ path shown on
# some older mirrors/notes of this dataset, which 404s.
#
# Usage: ./fetch_nclt.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

DATE="$(nclt_session_date "${NCLT_SEQUENCE}")"
if [[ -z "${DATE}" ]]; then
  echo "No known NCLT session date for sequence '${NCLT_SEQUENCE}'." >&2
  echo "Only ${NCLT_SEQUENCE:-nclt_4} is wired up in scripts/env.sh's nclt_session_date()." >&2
  echo "To add another sequence, find its date in the FAST-LIO2 paper's" >&2
  echo "Appendix Table VIII (arXiv 2107.06829) and add an entry there." >&2
  exit 1
fi

mkdir -p "${DATASET_DIR}"
cd "${DATASET_DIR}"

BASE_URL="https://s3.us-east-2.amazonaws.com/nclt.perl.engin.umich.edu"
VEL_TAR="${DATE}_vel.tar.gz"
SEN_TAR="${DATE}_sen.tar.gz"
GT_CSV="groundtruth_${DATE}.csv"

# Human-readable byte count (e.g. "5.3G"), or "unknown size" if the value
# can't be parsed - used only for the progress hint below, never for
# control flow.
human_size() {
  local bytes="$1"
  if [[ -z "${bytes}" || ! "${bytes}" =~ ^[0-9]+$ ]]; then
    echo "unknown size"
    return
  fi
  numfmt --to=iec --suffix=B "${bytes}" 2>/dev/null || echo "${bytes} bytes"
}

fetch_if_missing() {
  local url="$1" out="$2"
  if [[ -f "${out}" ]]; then
    echo "==> ${out} already present, skipping"
    return
  fi
  # These NCLT archives are multi-GB (velodyne_hits.bin alone is 16-20 GB
  # uncompressed) and can take many minutes over a slow/proxied link with
  # no console output in between; print the expected size up front, and
  # use dot-style progress (periodic "N% ... Nm Ns" lines, unlike the
  # default redrawing bar which needs a live terminal and renders as a
  # wall of carriage returns - or nothing at all - once piped to a log
  # file) so the log clearly shows it's advancing, not stuck.
  local content_length size_hint
  content_length="$(wget --spider -S "${url}" 2>&1 | sed -n 's/.*Content-Length: *\([0-9]*\).*/\1/p' | head -1)"
  size_hint="$(human_size "${content_length}")"
  echo "==> Downloading ${url} (${size_hint})"
  # -c resumes from an existing "${out}.part" left by an earlier
  # interrupted run instead of restarting the multi-GB transfer from 0%.
  wget -c --progress=dot:giga -O "${out}.part" "${url}"
  mv "${out}.part" "${out}"
}

fetch_if_missing "${BASE_URL}/velodyne_data/${VEL_TAR}" "${VEL_TAR}"
fetch_if_missing "${BASE_URL}/sensor_data/${SEN_TAR}" "${SEN_TAR}"
fetch_if_missing "${BASE_URL}/ground_truth/${GT_CSV}" "${GT_CSV}"

# Extract archives once. Confirmed by inspection: both archives extract
# into a "${DATE}/" subdirectory (e.g. "2012-01-15/velodyne_hits.bin",
# "2012-01-15/ms25.csv") - downstream scripts (convert_nclt_to_bag.py,
# extract_nclt_gt.py) still locate files via `find` under DATASET_DIR
# rather than hardcoding that nesting, so this keeps working even if a
# future/different session's archive is laid out slightly differently.
EXTRACT_MARKER=".extracted"
if [[ ! -f "${EXTRACT_MARKER}" ]]; then
  echo "==> Extracting ${VEL_TAR} and ${SEN_TAR}"
  tar -xzf "${VEL_TAR}"
  tar -xzf "${SEN_TAR}"
  touch "${EXTRACT_MARKER}"
else
  echo "==> Already extracted, skipping"
fi

VEL_BIN="$(find "${DATASET_DIR}" -type f -name velodyne_hits.bin | head -1)"
IMU_CSV="$(find "${DATASET_DIR}" -type f -name ms25.csv | head -1)"

if [[ -z "${VEL_BIN}" ]]; then
  echo "Could not find velodyne_hits.bin under ${DATASET_DIR} after extraction." >&2
  echo "Check ${VEL_TAR}'s actual contents (tar -tzf ${DATASET_DIR}/${VEL_TAR})." >&2
  exit 1
fi
if [[ -z "${IMU_CSV}" ]]; then
  echo "Could not find ms25.csv under ${DATASET_DIR} after extraction." >&2
  echo "Check ${SEN_TAR}'s actual contents (tar -tzf ${DATASET_DIR}/${SEN_TAR})." >&2
  exit 1
fi
if [[ ! -f "${DATASET_DIR}/${GT_CSV}" ]]; then
  echo "Missing ${DATASET_DIR}/${GT_CSV} after download." >&2
  exit 1
fi

echo "==> NCLT ${NCLT_SEQUENCE} (${DATE}) ready in ${DATASET_DIR}"
echo "    Velodyne: ${VEL_BIN}"
echo "    IMU:      ${IMU_CSV}"
echo "    Ground truth: ${DATASET_DIR}/${GT_CSV}"
