<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# Whisper Speech-to-Text

Local, private speech-to-text service powered by OpenAI Whisper.
No API key. No data leaves your machine.

The service is defined in the root [`docker-compose.yml`](../../docker-compose.yml) and joins the `fedaero` network.

## APIs

Whisper STT is only accessible via the nginx TLS reverse proxy. The container port is not exposed to the host.

| Endpoint | URL | Notes |
|----------|-----|-------|
| Web UI | https://localhost:5443 | Browser recording + file upload — browser mic enabled (via nginx) |
| Transcribe | `POST https://localhost:5443/transcribe` | Multipart `file` field (via nginx; use `-k` for self-signed cert) |
| Metrics | `http://localhost:5443/metrics` | Prometheus — internal Docker network only |

### Prometheus metrics

| Metric | Type | Description |
|--------|------|-------------|
| `stt_video_length_seconds_last` | Gauge | Duration of the last submitted audio/video (s) |
| `stt_video_length_seconds_total` | Counter | Cumulative audio duration processed (s) |
| `stt_processing_time_seconds_last` | Gauge | Transcription time for the last request (s) |
| `stt_processing_time_seconds_total` | Counter | Cumulative transcription time (s) |
| `stt_realtime_factor_last` | Gauge | Audio duration / processing time for last request (>1 = faster than real-time) |
| `stt_realtime_factor_sum` | Gauge | Same ratio computed from cumulative totals |

## Features

- Record directly from your microphone in the browser
- Upload any audio/video file (mp3, wav, ogg, webm, mp4, m4a, flac, …)
- Streaming chunked transcription — results appear as they are processed
- Auto-detected language shown in results
- Timestamped segment breakdown
- Copy to clipboard

## Model sizes

Set `WHISPER_MODEL` in the root `docker-compose.yml`:

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | ~150 MB | ~32× real-time | OK |
| `base` | ~290 MB | ~16× real-time | Good — **default** |
| `small` | ~970 MB | ~6× real-time | Better |
| `medium` | ~3 GB | ~2× real-time | Great |
| `large` | ~6 GB | ~1× real-time | Best |

`base` is the default — a good balance for everyday use on a CPU.
