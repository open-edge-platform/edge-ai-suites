#!/bin/bash
# filepath: services/rppg-service/scripts/prepare_test_video.sh

echo "=========================================="
echo "Preparing Test Video for RPPG Service"
echo "=========================================="

cd "$(dirname "$0")/.."

# Option 1: Download sample video
echo -e "\n1. Downloading sample test video..."
mkdir -p videos
wget -O videos/sample.mp4 "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi" || \
  curl -L -o videos/sample.mp4 "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi"

if [ -f "videos/sample.mp4" ]; then
  echo "✓ Video downloaded: videos/sample.mp4"
  ls -lh videos/sample.mp4
else
  echo "✗ Download failed. Please manually place a video file in videos/sample.mp4"
  echo "  Video requirements:"
  echo "    - Resolution: >100x100 pixels"
  echo "    - Duration: >1 second"
  echo "    - Format: MP4, AVI, or MOV"
  exit 1
fi

# Option 2: Download model (49 MB)
echo -e "\n2. Downloading MTTS-CAN model..."
mkdir -p models
wget -O models/mtts_can.hdf5 "https://github.com/xliucs/MTTS-CAN/releases/download/v1.0/mtts_can.hdf5" || \
  curl -L -o models/mtts_can.hdf5 "https://github.com/xliucs/MTTS-CAN/releases/download/v1.0/mtts_can.hdf5"

if [ -f "models/mtts_can.hdf5" ]; then
  echo "✓ Model downloaded: models/mtts_can.hdf5"
  ls -lh models/mtts_can.hdf5
else
  echo "✗ Model download failed"
  echo "  Please manually download from:"
  echo "  https://github.com/xliucs/MTTS-CAN/releases/download/v1.0/mtts_can.hdf5"
  echo "  and place in models/mtts_can.hdf5"
  exit 1
fi

echo -e "\n=========================================="
echo "✓ Test assets prepared successfully!"
echo "=========================================="
echo ""
echo "Video: $(ls -lh videos/sample.mp4 2>/dev/null || echo 'NOT FOUND')"
echo "Model: $(ls -lh models/mtts_can.hdf5 2>/dev/null || echo 'NOT FOUND')"
echo ""