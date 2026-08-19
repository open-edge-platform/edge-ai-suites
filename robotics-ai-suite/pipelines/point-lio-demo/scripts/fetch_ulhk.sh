#!/usr/bin/env bash
# Download the UrbanLoco sequence configured in env.sh.
#
# UrbanLoco (github.com/weisongwen/UrbanLoco, PolyU IPN-Lab, ICRA 2020) hosts
# its files on Google Drive, which - unlike NCLT's plain S3 bucket - requires a
# large-file "can't scan for viruses" confirmation step that plain
# wget/curl can't complete on their own. This script tries the automated
# `gdown` route first (installed by install_deps.sh); if that's too slow or
# fails outright (Google Drive rate-limits are common on shared/proxied
# networks), it prints the exact manual-download URL, method, and target
# directory below and exits non-fatally so reproduce_all.sh can simply be
# re-run once the file has been placed by hand.
#
# Usage: ./fetch_ulhk.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SESSION="$(ulhk_session_name "${ULHK_SEQUENCE}")"
GDRIVE_ID="$(ulhk_gdrive_id "${ULHK_SEQUENCE}")"
if [[ -z "${SESSION}" || -z "${GDRIVE_ID}" ]]; then
  echo "No known UrbanLoco session/Google Drive ID for sequence '${ULHK_SEQUENCE}'." >&2
  echo "Only ulhk_4 is wired up in scripts/env.sh's ulhk_session_name()/ulhk_gdrive_id()." >&2
  exit 1
fi

mkdir -p "${DATASET_DIR}"

# `pip install --user` puts console scripts (gdown included) in ~/.local/bin,
# which isn't guaranteed to be on PATH (e.g. a non-interactive SSH session,
# confirmed missing there in practice) - use it explicitly rather than
# relying on gdown already being on PATH.
export PATH="${HOME}/.local/bin:${PATH}"

manual_instructions() {
  cat >&2 <<EOF

==> Automated download did not complete. To fetch it manually instead:
    1. Go to the official UrbanLoco GitHub repo and download the
       ${SESSION} session yourself, using whatever method works on your
       network (the download links it points to may require a
       proxy/mirror/VPN depending on where you are - this script can't
       pick that for you):
         https://github.com/weisongwen/UrbanLoco
    2. Place the downloaded file at exactly this path:
         ${ULHK_RAW_FILE}
    3. Re-run this script (./fetch_ulhk.sh) - it will detect the file is
       already present and skip straight to done, or just continue on to
       ./convert_ulhk_to_bag.sh directly.
EOF
}

if [[ -f "${ULHK_RAW_FILE}" ]]; then
  echo "==> ${ULHK_RAW_FILE} already present, skipping download"
  exit 0
fi

# The raw file itself is only an intermediate: once convert_ulhk_to_bag.sh
# has produced BAG_DIR, there's nothing left for this script to fetch, even
# if the raw file was never placed at ULHK_RAW_FILE (e.g. the converted bag
# was copied in directly from elsewhere, as happened on the PTL board).
if [[ -d "${BAG_DIR}" ]]; then
  echo "==> ${BAG_DIR} (converted bag) already present, skipping download"
  exit 0
fi

if ! command -v gdown >/dev/null 2>&1; then
  echo "gdown not found (run ./install_deps.sh first)." >&2
  manual_instructions
  exit 1
fi

echo "==> Downloading UrbanLoco ${ULHK_SEQUENCE} (${SESSION}) via gdown"
echo "    (Google Drive downloads can be slow/rate-limited on some networks -"
echo "    if this hangs or fails, Ctrl-C and follow the manual instructions"
echo "    this script prints below.)"
if gdown -c "${GDRIVE_ID}" -O "${ULHK_RAW_FILE}.part"; then
  mv "${ULHK_RAW_FILE}.part" "${ULHK_RAW_FILE}"
  echo "==> Downloaded to ${ULHK_RAW_FILE}"
else
  rm -f "${ULHK_RAW_FILE}.part"
  echo "gdown failed or was interrupted." >&2
  manual_instructions
  exit 1
fi
