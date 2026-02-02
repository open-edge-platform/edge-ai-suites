#!/bin/bash

echo "=========================================="
echo "Preparing Test Video for RPPG Service"
echo "=========================================="

cd "$(dirname "$0")/.."

mkdir -p videos
wget -O videos/sample.mp4 "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi" || \
  curl -L -o videos/sample.mp4 "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi"

if [ ! -f "videos/sample.mp4" ]; then
  echo "Download failed for sample video"
  exit 1
fi

mkdir -p models
wget -O models/mtts_can.hdf5 "https://github.com/xliucs/MTTS-CAN/releases/download/v1.0/mtts_can.hdf5" || \
  curl -L -o models/mtts_can.hdf5 "https://github.com/xliucs/MTTS-CAN/releases/download/v1.0/mtts_can.hdf5"

if [ ! -f "models/mtts_can.hdf5" ]; then
  echo "Download failed for model"
  exit 1
fi

echo "Test assets prepared successfully."
