# Release Notes

## 2026.1.3
### Relase Date: 16 Jan 2026

- Initial release of Live Video Captioning
- Docker Compose stack integrating DLStreamer pipeline server, WebRTC signaling (mediamtx), TURN (coturn), and FastAPI dashboard
- Multi-model discovery from `ov_models/`
- Live captions via SSE and live metrics via WebSockets

## Upgrade Notes

- If you change `.env` values (ports, `HOST_IP`, model paths), restart the stack: `docker compose down && docker compose up `.
