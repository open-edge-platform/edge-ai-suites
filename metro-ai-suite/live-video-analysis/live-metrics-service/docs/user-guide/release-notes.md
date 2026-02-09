# Release Notes

## Version 1.0.0-rc.0

**Release Date:** January 30, 2026

### Features

- WebSocket relay for real-time metrics streaming
- Single collector connection with policy enforcement
- Multi-client broadcast support with unlimited connections
- Health monitoring endpoints (`/health`, `/api/health`)
- Metrics status endpoint (`/api/metrics/status`)
- Configurable CORS support
- Docker container with non-root user
- Environment-based configuration
- Automatic client connection cleanup
- Metrics format normalization

### Components

- FastAPI-based service
- Uvicorn ASGI server
- WebSocket support for collector and clients
- Integration with Telegraf collectors
- Docker Compose deployment configuration

### Configuration Options

- `METRICS_PORT`: Service port (default: 9090)
- `LOG_LEVEL`: Logging verbosity (default: INFO)
- `CORS_ORIGINS`: CORS origin allowlist (default: *)
- `TARGET_SERVICE_URL`: Optional service polling URL
- `METRICS_ENDPOINT`: Polling endpoint path
- `POLL_INTERVAL_SECONDS`: Polling frequency

### Known Limitations

- Single collector connection only
- No metrics persistence
- WebSocket-only protocol
- No authentication/authorization

### Docker Images

- `intel/live-metrics-service:1.0.0-rc.0`
- Compatible with `intel/vippet-collector:2025.2.0`
