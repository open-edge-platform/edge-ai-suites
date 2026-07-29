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
CONFIG_FILE=""

# ✅ Usage function
usage() {
    echo "Usage: $0 -i <video_file> [-i <video_file> ...] [-o <rtsp_url> ...]"
    echo "   or: $0 -c <config.json>"
    echo ""
    echo "Example:"
    echo "  $0 -i video1.mp4"
    echo "  $0 -i video1.mp4 -i video2.mp4"
    echo "  $0 -i video1.mp4 -o rtsp://127.0.0.1:8554/cam1"
    echo "  $0 -i video1.mp4 -i video2.mp4 -o rtsp://127.0.0.1:8554/cam1 -o rtsp://127.0.0.1:8554/cam2"
    echo "  $0 -c streams.json"
    echo ""
    echo "Notes:"
    echo "  - Use -i multiple times for multiple input videos."
    echo "  - Use -c to load inputs/outputs from a JSON file."
    echo "  - jq is required for -c mode (auto-installed if missing)."
    echo "  - If -o is omitted, output URLs default to:"
    echo "      rtsp://127.0.0.1:8554/stream1, stream2, ..."
    echo "  - If -o is provided, count must match number of -i arguments."
    echo "  - JSON format for -c:"
    echo "      {\"inputs\": [\"video1.mp4\", \"video2.mp4\"],"
    echo "       \"outputs\": [\"rtsp://127.0.0.1:8554/cam1\", \"rtsp://127.0.0.1:8554/cam2\"]}"
    echo "    (\"outputs\" is optional)"
    exit 1
}

# ✅ Parse arguments
while getopts "i:o:c:h" opt; do
  case $opt in
    i) VIDEO_FILES+=("$OPTARG") ;;
    o) STREAM_URLS+=("$OPTARG") ;;
    c) CONFIG_FILE="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

# Validate argument mode combinations.
if [ -n "$CONFIG_FILE" ] && { [ ${#VIDEO_FILES[@]} -gt 0 ] || [ ${#STREAM_URLS[@]} -gt 0 ]; }; then
    echo "[ERROR] Use either -c <config.json> or -i/-o arguments, not both"
    usage
fi

# Load configuration from JSON file when -c is used.
if [ -n "$CONFIG_FILE" ]; then
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "[ERROR] Config file does not exist: $CONFIG_FILE"
        exit 1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        echo "[INFO] jq not found. Installing..."
        sudo apt update
        sudo apt install -y jq
    fi

    if ! jq -e 'type == "object"' "$CONFIG_FILE" >/dev/null; then
        echo "[ERROR] Config root must be a JSON object"
        exit 1
    fi

    if ! jq -e '.inputs | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)' "$CONFIG_FILE" >/dev/null; then
        echo "[ERROR] \"inputs\" must be a non-empty array of non-empty strings"
        exit 1
    fi

    if ! jq -e 'if has("outputs") then (.outputs | type == "array" and all(.[]; type == "string" and length > 0)) else true end' "$CONFIG_FILE" >/dev/null; then
        echo "[ERROR] \"outputs\" must be an array of non-empty strings when provided"
        exit 1
    fi

    CONFIG_DIR="$(cd "$(dirname "$CONFIG_FILE")" && pwd)"

    while IFS= read -r input_file; do
        if [[ "$input_file" = /* ]]; then
            VIDEO_FILES+=("$input_file")
        else
            VIDEO_FILES+=("$CONFIG_DIR/$input_file")
        fi
    done < <(jq -r '.inputs[]' "$CONFIG_FILE")

    if jq -e 'has("outputs")' "$CONFIG_FILE" >/dev/null; then
        while IFS= read -r output_url; do
            STREAM_URLS+=("$output_url")
        done < <(jq -r '.outputs[]' "$CONFIG_FILE")
    fi

    if [ ${#VIDEO_FILES[@]} -eq 0 ]; then
        echo "[ERROR] Config file did not produce any input entries"
        exit 1
    fi
fi

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
