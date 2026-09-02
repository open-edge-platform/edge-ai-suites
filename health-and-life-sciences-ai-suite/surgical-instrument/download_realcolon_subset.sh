#!/bin/bash
# Download a small subset of the REAL-Colon dataset (7 of 60 studies, ~74 GB)
# from the public figshare article. Enough to train and validate the
# Surgical Instrument app without pulling the full ~880 GB corpus.
#
# Dataset home: https://github.com/cosmoimd/real-colon-dataset
# Figshare article: https://figshare.com/articles/dataset/REAL-Colon_dataset/22202866
#
# Usage:
#   bash download_realcolon_subset.sh [target-dir]
#     target-dir defaults to datasets/REAL-Colon/raw

set -euo pipefail

DIR="${1:-datasets/REAL-Colon/raw}"
mkdir -p "$DIR"

# 7 studies (~74 GB total). Adjust this list if you want more or fewer.
STUDIES=(
  "001-001"
  "001-002"
  "001-005"
  "001-007"
  "002-008"
  "002-010"
  "004-008"
)

ARTICLE_ID="22202866"
API="https://api.figshare.com/v2/articles/${ARTICLE_ID}/files"

command -v curl    >/dev/null || { echo "ERROR: curl is required";    exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 is required"; exit 1; }
command -v tar     >/dev/null || { echo "ERROR: tar is required";     exit 1; }

echo "[subset] fetching file list from figshare (article ${ARTICLE_ID})..."
FILES_JSON=$(curl -sfL "$API")

for study in "${STUDIES[@]}"; do
  for suffix in "_frames.tar.gz" "_annotations.tar.gz"; do
    name="${study}${suffix}"
    url=$(printf '%s' "$FILES_JSON" | python3 -c "
import json, sys
target = '$name'
for f in json.load(sys.stdin):
    if f.get('name') == target:
        print(f.get('download_url', ''))
        break
")
    if [ -z "$url" ]; then
      echo "[subset] WARN: $name not found on figshare, skipping"
      continue
    fi
    out="$DIR/$name"
    if [ -f "$out" ] && [ -s "$out" ]; then
      echo "[subset] $name already present, skipping"
      continue
    fi
    echo "[subset] downloading $name"
    curl -L --fail --retry 3 --retry-delay 5 -o "$out" "$url"
  done
done

echo "[subset] extracting archives..."
for f in "$DIR"/*.tar.gz; do
  [ -f "$f" ] || continue
  tar -xzf "$f" -C "$DIR"
done

echo "[subset] done. $(du -sh "$DIR" | cut -f1) in $DIR"
