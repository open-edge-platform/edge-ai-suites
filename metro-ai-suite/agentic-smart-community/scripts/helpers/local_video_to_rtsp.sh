#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Loop a local video and publish it to an RTSP URL.
#
# Usage:
#   bash scripts/helpers/local_video_to_rtsp.sh /path/to/video.mp4 [RTSP_URL]
#
# Example:
#   bash scripts/helpers/local_video_to_rtsp.sh video.mp4 rtsp://localhost:8555/live/test
#
# Environment:
#   MEDIAMTX_BIN=/path/to/mediamtx  # default: ~/.local/bin/mediamtx

set -euo pipefail


VIDEO_FILE="${1:-}"
RTSP_URL="${2:-rtsp://localhost:8555/live/test}"

MEDIAMTX_BIN="${MEDIAMTX_BIN:-$HOME/.local/bin/mediamtx}"
RUN_DIR=""
MEDIAMTX_PID=""
FFMPEG_PID=""

usage() {
	sed -n '4,13p' "$0"
}

cleanup() {
	local pid
	for pid in "$FFMPEG_PID" "$MEDIAMTX_PID"; do
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
			wait "$pid" 2>/dev/null || true
		fi
	done
	[[ -n "$RUN_DIR" ]] && rm -rf "$RUN_DIR"
}
trap cleanup EXIT INT TERM

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
	usage
	exit 0
fi

if [[ ! "$RTSP_URL" =~ ^rtsp://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+):([0-9]{1,5})/([-A-Za-z0-9._~%]+(/[-A-Za-z0-9._~%]+)*)$ ]]; then
	echo "ERROR: Invalid RTSP URL: $RTSP_URL" >&2
	echo "Expected format: rtsp://host:port/path" >&2
	exit 1
fi
RTSP_PORT="$((10#${BASH_REMATCH[2]}))"
RTSP_PATH="${BASH_REMATCH[3]}"
if (( RTSP_PORT < 1 || RTSP_PORT > 65535 )); then
	echo "ERROR: RTSP port must be between 1 and 65535: $RTSP_PORT" >&2
	exit 1
fi

command -v ffmpeg >/dev/null 2>&1 || { echo "ERROR: 'ffmpeg' not found in PATH." >&2; exit 1; }
[[ -x "$MEDIAMTX_BIN" ]] || { echo "ERROR: MediaMTX not found or not executable: $MEDIAMTX_BIN" >&2; exit 1; }
[[ -f "$VIDEO_FILE" && -r "$VIDEO_FILE" ]] || { echo "ERROR: Video file not found or unreadable: $VIDEO_FILE" >&2; exit 1; }

if command -v ss >/dev/null 2>&1 && ss -H -ltn "sport = :$RTSP_PORT" 2>/dev/null | grep -q .; then
	echo "ERROR: TCP port $RTSP_PORT is already in use." >&2
	exit 1
fi

RUN_DIR="$(mktemp -d)"
MEDIAMTX_CONFIG="$RUN_DIR/mediamtx.yml"
MEDIAMTX_LOG="$RUN_DIR/mediamtx.log"
FFMPEG_LOG="$RUN_DIR/ffmpeg.log"

printf '%s\n' \
	'logLevel: warn' \
	'rtsp: true' \
	'rtspTransports: [tcp]' \
	"rtspAddress: :${RTSP_PORT}" \
	'rtmp: false' \
	'hls: false' \
	'webrtc: false' \
	'srt: false' \
	'api: false' \
	'paths:' \
	"  ${RTSP_PATH}:" \
	'    source: publisher' >"$MEDIAMTX_CONFIG"

"$MEDIAMTX_BIN" "$MEDIAMTX_CONFIG" >"$MEDIAMTX_LOG" 2>&1 &
MEDIAMTX_PID=$!

for _ in {1..20}; do
	if command -v ss >/dev/null 2>&1 && ss -H -ltn "sport = :$RTSP_PORT" 2>/dev/null | grep -q .; then
		break
	fi
	if ! kill -0 "$MEDIAMTX_PID" 2>/dev/null; then
		echo "ERROR: MediaMTX failed to start:" >&2
		tail -n 20 "$MEDIAMTX_LOG" >&2
		exit 1
	fi
	sleep 0.1
done

ffmpeg -nostdin -hide_banner -loglevel warning \
	-stream_loop -1 -re -i "$VIDEO_FILE" \
	-c copy -f rtsp -rtsp_transport tcp "$RTSP_URL" >"$FFMPEG_LOG" 2>&1 &
FFMPEG_PID=$!

sleep 0.5
if ! kill -0 "$FFMPEG_PID" 2>/dev/null; then
	echo "ERROR: ffmpeg failed to publish the video:" >&2
	tail -n 20 "$FFMPEG_LOG" >&2
	exit 1
fi

printf 'RTSP stream: %s\n' "$RTSP_URL"
printf 'Press Ctrl-C to stop.\n'
wait "$FFMPEG_PID"
