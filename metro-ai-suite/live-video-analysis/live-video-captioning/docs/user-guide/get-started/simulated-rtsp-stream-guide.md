# Setup Simulated RTSP Stream

This guide explains how to set up a simulated RTSP stream. It includes a script that helps you quickly create a looped RTSP stream from a local video file.

The [`setup_proxy_rtsp.sh`](../../../scripts/setup_proxy_rtsp.sh) script allows you to:

- Stream one or more local video files as live RTSP feeds
- Loop all videos indefinitely
- Publish multiple RTSP endpoints in one script run

The setup uses:

- **FFmpeg** → for video streaming
- **MediaMTX (RTSP server)** → to serve the stream

## Prerequisites

Before you run the script, make sure the following prerequisites are met:

✅ System Requirements

- Ubuntu Linux (required)
- Bash shell
- Internet access (for installation)

The script checks `/etc/os-release` and runs only on Ubuntu.
It exits with an error on `Edge Microvisor Toolkit` and other non-Ubuntu distributions.

✅ Required Tools

The script automatically installs:
- ffmpeg

Ensure that `Docker` is installed on your system.

## Script Setup

1. Go to the scripts directory.

```bash
cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning/scripts
```

2. Make the script executable.

```bash
chmod +x setup_proxy_rtsp.sh
```

## Usage

### Basic Usage

Before running the command, make sure the video file exists.

```bash
./setup_proxy_rtsp.sh -i <your-input-video-file>
```

👉 Default stream URL for one input:
```text
rtsp://127.0.0.1:8554/stream1
```

### Multiple Inputs in One Run

Use `-i` multiple times to stream multiple input videos in a single script run.

Each input video is published to its own RTSP endpoint in this mode (one-to-one mapping), not to a shared endpoint.

```bash
./setup_proxy_rtsp.sh -i video1.mp4 -i video2.mp4 -i video3.mp4
```

👉 Auto-generated default stream URLs:
```text
rtsp://127.0.0.1:8554/stream1  # video1.mp4
rtsp://127.0.0.1:8554/stream2  # video2.mp4
rtsp://127.0.0.1:8554/stream3  # video3.mp4
```

### Custom RTSP Endpoint

```bash
./setup_proxy_rtsp.sh -i <your-input-video-file> -o rtsp://127.0.0.1:8554/cam1
```

👉 Custom stream URL:
```text
rtsp://127.0.0.1:8554/cam1
```

### Multiple Custom RTSP Endpoints

Use `-o` multiple times to map each input video to a specific output URL.

```bash
./setup_proxy_rtsp.sh \
	-i video1.mp4 -i video2.mp4 \
	-o rtsp://127.0.0.1:8554/cam1 \
	-o rtsp://127.0.0.1:8554/cam2
```

### Config File Input (JSON)

For multiple streams, you can provide all input/output mappings in a JSON file.

1. Create a JSON config file.

Example with custom outputs:

```json
{
	"inputs": [
		"video1.mp4",
		"video2.mp4"
	],
	"outputs": [
		"rtsp://127.0.0.1:8554/cam1",
		"rtsp://127.0.0.1:8554/cam2"
	]
}
```

Example without outputs (auto-generates `stream1`, `stream2`, ...):

```json
{
	"inputs": [
		"video1.mp4",
		"video2.mp4"
	]
}
```

2. Run the script with the config file.

```bash
./setup_proxy_rtsp.sh -c <your-config-file>.json
```

Notes:

- Use either `-c` or `-i`/`-o` in a single run (do not mix them).
- Relative input paths in JSON are resolved relative to the JSON file location.
- `-c` mode uses `jq`, and the script installs it automatically if missing.

Important:

- If `-o` is omitted, the script auto-generates `stream1`, `stream2`, ...
- If `-o` is provided, the number of `-o` values must match the number of `-i` values.

### Help Option

```bash
./setup_proxy_rtsp.sh -h
```

## Viewing the stream

To verify outputs, open the RTSP streams in VLC on the same machine.

Examples:

```text
rtsp://127.0.0.1:8554/stream1
rtsp://127.0.0.1:8554/stream2
rtsp://127.0.0.1:8554/cam1
```

You can also access the stream from other devices on the same network by using the IP address of the host running the script.

Replace `127.0.0.1` with the host IP address:

```text
# Example
rtsp://<host-ip>:8554/stream1
```

The stream is now ready to use in the Live Video Captioning application.

## Stopping the Stream

### Stop FFmpeg

From the script terminal, press:

```text
CTRL + C
```

### Stop RTSP Server

```bash
docker stop mediamtx-server
```