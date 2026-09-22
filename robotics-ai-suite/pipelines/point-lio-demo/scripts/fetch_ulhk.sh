#!/usr/bin/env bash
# Check whether the UrbanLoco sequence configured in env.sh is already
# present, and if not, print exactly where to get it and where to place it.
#
# UrbanLoco (github.com/weisongwen/UrbanLoco, PolyU IPN-Lab, ICRA 2020) does
# not have a scriptable download: its official Google Drive link cannot be
# fetched automatically (large-file "can't scan for viruses" confirmation
# gate) and, in practice, is often unreachable at all from a corporate
# network even with an account. The GitHub repo's own README also lists
# Dropbox and Baidu Netdisk mirrors for every Hong Kong sequence (same
# shared-folder link for all of them) - those are what this script points
# to. There is deliberately no gdown/automated-download attempt here: a
# human downloads the file once, by hand, and places it at the path below.
#
# Usage: ./fetch_ulhk.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SESSION="$(ulhk_session_name "${ULHK_SEQUENCE}")"
if [[ -z "${SESSION}" ]]; then
  echo "No known UrbanLoco session for sequence '${ULHK_SEQUENCE}'." >&2
  echo "Only ulhk_4 is wired up in scripts/env.sh's ulhk_session_name()." >&2
  exit 1
fi

mkdir -p "${DATASET_DIR}"

if [[ -f "${ULHK_RAW_FILE}" ]]; then
  echo "==> ${ULHK_RAW_FILE} already present, skipping download"
  exit 0
fi

# The raw file itself is only an intermediate: once convert_ulhk_to_bag.sh
# has produced BAG_DIR, there's nothing left to fetch, even if the raw file
# was never placed at ULHK_RAW_FILE (e.g. the converted bag was copied in
# directly from elsewhere).
if [[ -d "${BAG_DIR}" ]]; then
  echo "==> ${BAG_DIR} (converted bag) already present, skipping download"
  exit 0
fi

cat >&2 <<EOF
UrbanLoco sequence '${ULHK_SEQUENCE}' (${SESSION}) not found at
${ULHK_RAW_FILE}.

This dataset has no scriptable download - Google Drive requires a manual
confirmation step and is frequently unreachable from corporate networks even
with an account. Download it by hand instead, from the ${SESSION} row of the
official UrbanLoco Hong Kong dataset table
(github.com/weisongwen/UrbanLoco, section "2. Hong Kong Dataset"):

  1. Dropbox: https://www.dropbox.com/scl/fo/zrsmoddbq96t4go1wbxwp/AJw_DGVXng06DmLx9j9iQMs?rlkey=rk11n8tt62ejbg8mbixrm6quz&e=1&st=j7sy3izj&dl=0
     Baidu Netdisk (百度网盘): https://pan.baidu.com/s/1-5d8xM1tzfsSSueTiU6-MQ?pwd=sufc
     (same shared folder for every Hong Kong sequence - open the
     ${SESSION} entry inside it)
  2. Place the downloaded file at exactly this path:
       ${ULHK_RAW_FILE}
  3. Re-run this script (./fetch_ulhk.sh) - it will detect the file is
     already present and skip straight to done, or just continue on to
     ./convert_ulhk_to_bag.sh directly.
EOF
exit 1
