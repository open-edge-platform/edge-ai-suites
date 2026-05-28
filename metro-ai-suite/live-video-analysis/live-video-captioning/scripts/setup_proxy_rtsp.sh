#!/bin/bash

set -e

# Ensure this script runs only on supported OS.
if grep -q '^ID=ubuntu' /etc/os-release 2>/dev/null; then
    echo "[INFO] Detected Ubuntu. Proceeding..."
elif grep -q '^ID="Edge Microvisor Toolkit"' /etc/os-release 2>/dev/null || \
    grep -q '^ID=Edge Microvisor Toolkit' /etc/os-release 2>/dev/null; then
    echo "[ERROR] This is not Ubuntu. This script is not supported on Edge Microvisor Toolkit."
    exit 1
else
    echo "[ERROR] Unsupported OS. This script supports Ubuntu only."
    exit 1
fi

# ✅ Default values
declare -a VIDEO_FILES=()
declare -a STREAM_URLS=()
DEFAULT_STREAM_BASE="rtsp://127.0.0.1:8554/stream"

# ✅ Usage function
usage() {
    echo "Usage: $0 -i <video_file> [-i <video_file> ...] [-o <rtsp_url> ...]"
    echo ""
    echo "Example:"
    echo "  $0 -i video1.mp4"
    echo "  $0 -i video1.mp4 -i video2.mp4"
    echo "  $0 -i video1.mp4 -o rtsp://127.0.0.1:8554/cam1"
    echo "  $0 -i video1.mp4 -i video2.mp4 -o rtsp://127.0.0.1:8554/cam1 -o rtsp://127.0.0.1:8554/cam2"
    echo ""
    echo "Notes:"
    echo "  - Use -i multiple times for multiple input videos."
    echo "  - If -o is omitted, output URLs default to:"
    echo "      rtsp://127.0.0.1:8554/stream1, stream2, ..."
    echo "  - If -o is provided, count must match number of -i arguments."
    exit 1
}

# ✅ Parse arguments
while getopts "i:o:h" opt; do
  case $opt in
    i) VIDEO_FILES+=("$OPTARG") ;;
    o) STREAM_URLS+=("$OPTARG") ;;
    h) usage ;;
    *) usage ;;
  esac
done

# ✅ Validate input
if [ ${#VIDEO_FILES[@]} -eq 0 ]; then
    echo "[ERROR] No video file provided"
    usage
fi

# Validate all input files exist.
for video in "${VIDEO_FILES[@]}"; do
    if [ ! -f "$video" ]; then
        echo "[ERROR] File does not exist: $video"
        exit 1
    fi
done

# Validate output mapping.
if [ ${#STREAM_URLS[@]} -gt 0 ] && [ ${#STREAM_URLS[@]} -ne ${#VIDEO_FILES[@]} ]; then
    echo "[ERROR] Number of output URLs must match number of input videos"
    echo "[ERROR] Inputs: ${#VIDEO_FILES[@]}, Outputs: ${#STREAM_URLS[@]}"
    exit 1
fi

# Auto-generate default output URLs when none are provided.
if [ ${#STREAM_URLS[@]} -eq 0 ]; then
    for idx in "${!VIDEO_FILES[@]}"; do
        STREAM_URLS+=("${DEFAULT_STREAM_BASE}$((idx + 1))")
    done
fi

echo "=== RTSP Proxy Setup Starting ==="
echo "[INFO] Total input videos: ${#VIDEO_FILES[@]}"
for idx in "${!VIDEO_FILES[@]}"; do
    echo "[INFO] Stream $((idx + 1)): ${VIDEO_FILES[$idx]} -> ${STREAM_URLS[$idx]}"
done

# ✅ 1. Check ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[INFO] ffmpeg not found. Installing..."
    sudo apt update
    sudo apt install -y ffmpeg
else
    echo "[INFO] ffmpeg already installed"
fi

# ✅ 2. Check Docker
if ! command -v docker >/dev/null 2>&1; then
    echo "[ERROR] Docker is not installed. Please install docker first."
    exit 1
fi

# ✅ 3. Pull MediaMTX
echo "[INFO] Pulling MediaMTX image..."
docker pull bluenviron/mediamtx

# ✅ 4. Start MediaMTX server (if not already running)
if ! docker ps | grep -q mediamtx-server; then
    echo "[INFO] Starting MediaMTX server..."
    docker rm -f mediamtx-server 2>/dev/null || true
    docker run -d \
        --name mediamtx-server \
        -p 8554:8554 \
        bluenviron/mediamtx
    sleep 2
else
    echo "[INFO] MediaMTX already running"
fi

# ✅ 5. Start FFmpeg streams
echo "[INFO] Starting RTSP loop streams..."

declare -a FFMPEG_PIDS=()

cleanup() {
    if [ ${#FFMPEG_PIDS[@]} -gt 0 ]; then
        echo "[INFO] Stopping FFmpeg stream processes..."
        kill "${FFMPEG_PIDS[@]}" 2>/dev/null || true
    fi
}

trap cleanup INT TERM EXIT

for idx in "${!VIDEO_FILES[@]}"; do
    video="${VIDEO_FILES[$idx]}"
    url="${STREAM_URLS[$idx]}"

    ffmpeg -re -stream_loop -1 -i "$video" \
      -c:v libx264 -preset ultrafast -tune zerolatency \
      -profile:v baseline -level 3.1 \
      -c:a aac -b:a 128k -ar 44100 \
      -r 30 -g 60 -keyint_min 30 \
      -avoid_negative_ts make_zero \
      -fflags +genpts \
      -rtsp_transport tcp -rtsp_flags prefer_tcp \
      -muxdelay 0.1 \
      -f rtsp "$url" &

    FFMPEG_PIDS+=("$!")
    echo "[INFO] Started stream $((idx + 1)) with PID ${FFMPEG_PIDS[$idx]}"
done

echo "[INFO] All streams are running. Press Ctrl+C to stop."
wait
