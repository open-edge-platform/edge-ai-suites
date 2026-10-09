#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Prepare the DAVIS demo dataset on the host, in the directory shared with the
# dataprep microservice. Half of the selected categories are turned into videos,
# the other half into sampled still images, and a meta/<basename>.json sidecar is
# written for each item so the UI's camera and date filters have something to
# filter on.
set -euo pipefail

DATA_PATH="${HOST_DATA_PATH:-$HOME/data}"
SUBSET_DIR="${DATA_PATH}/DAVIS/subset"
META_DIR="${SUBSET_DIR}/meta"
ZIP_NAME="DAVIS-2017-test-dev-480p.zip"
ZIP_URL="https://data.vision.ee.ethz.ch/csergi/share/davis/${ZIP_NAME}"
# Every Nth frame is kept for the image categories.
FRAME_SKIP="${FRAME_SKIP:-20}"
CATEGORIES=(car-race deer guitar-violin gym helicopter carousel
            monkeys-trees golf rollercoaster horsejump-stick planes-crossing tractor)

for tool in curl unzip ffmpeg; do
  command -v "${tool}" >/dev/null 2>&1 || { echo "ERROR: '${tool}' is required." >&2; exit 1; }
done

mkdir -p "${DATA_PATH}"
if [ ! -f "${DATA_PATH}/${ZIP_NAME}" ]; then
  echo "Downloading ${ZIP_NAME} to ${DATA_PATH}"
  curl --retry 5 --continue-at - -o "${DATA_PATH}/${ZIP_NAME}" "${ZIP_URL}"
fi

if [ ! -d "${DATA_PATH}/DAVIS/JPEGImages" ]; then
  echo "Unzipping ${ZIP_NAME}"
  unzip -q "${DATA_PATH}/${ZIP_NAME}" -d "${DATA_PATH}"
fi

mkdir -p "${SUBSET_DIR}" "${META_DIR}"

write_sidecar() {
  # $1: basename without extension, $2: camera id, $3: capture date (YYYYMMDD)
  printf '{\n  "camera": "%s",\n  "capture_date": %s\n}\n' "$2" "$3" >"${META_DIR}/$1.json"
}

index=0
half=$(( ${#CATEGORIES[@]} / 2 ))
for category in "${CATEGORIES[@]}"; do
  src="${DATA_PATH}/DAVIS/JPEGImages/480p/${category}"
  if [ ! -d "${src}" ]; then
    echo "Skipping missing category: ${category}"
    index=$(( index + 1 ))
    continue
  fi

  camera="camera_$(( index % 4 + 1 ))"
  capture_date=$(date -d "2026-01-01 +${index} days" +%Y%m%d)

  if [ "${index}" -lt "${half}" ]; then
    # Image category: keep every FRAME_SKIP-th frame.
    frame=0
    for image in "${src}"/*.jpg; do
      if [ $(( frame % FRAME_SKIP )) -eq 0 ]; then
        name="${category}_$(basename "${image}" .jpg)"
        cp "${image}" "${SUBSET_DIR}/${name}.jpg"
        write_sidecar "${name}" "${camera}" "${capture_date}"
      fi
      frame=$(( frame + 1 ))
    done
  else
    # Video category: encode the frame sequence into a single clip.
    ffmpeg -y -loglevel error -framerate 24 -pattern_type glob \
      -i "${src}/*.jpg" -c:v libx264 -pix_fmt yuv420p "${SUBSET_DIR}/${category}.mp4"
    write_sidecar "${category}" "${camera}" "${capture_date}"
  fi
  echo "Prepared ${category}"
  index=$(( index + 1 ))
done

echo "Demo dataset ready at ${SUBSET_DIR}"
