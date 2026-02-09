# API Reference

Complete API documentation for the Metrics Service.

## WebSocket Endpoints

### `WS /ws/collector`

**Purpose:** Single connection point for metrics collectors (Telegraf).

**Protocol:**
- Only one collector can connect at a time
- Receives JSON metric arrays from Telegraf
- Connection rejected with `WS_1008_POLICY_VIOLATION` if collector already connected

**Input Format (from Telegraf):**

```json
[
  {
    "name": "cpu",
    "tags": {"cpu": "cpu-total", "host": "hostname"},
    "fields": {"usage_user": 12.5},
    "timestamp": 1767758563
  }
]
```

### `WS /ws/clients`

**Purpose:** Multiple client connections for receiving live metrics.

**Protocol:**
- Unlimited concurrent connections
- Receives metrics broadcast from collector
- Messages from clients are ignored (connection kept alive)

**Output Format (to clients):**

```json
{
  "metrics": [
    {
      "name": "cpu",
      "tags": {"cpu": "cpu-total", "host": "hostname"},
      "fields": {"usage_user": 12.5},
      "timestamp": 1767758563
    },
    {
      "name": "mem",
      "tags": {"host": "hostname"},
      "fields": {"used_percent": 45.2},
      "timestamp": 1767758563
    }
  ]
}
```

## REST Endpoints

### `GET /health`

Basic health check.

**Response:**

```json
{"status": "healthy"}
```

### `GET /api/health`

Detailed health with service status.

**Response:**

```json
{
  "status": "healthy",
  "collector_connected": true,
  "clients_connected": 3,
  "poller_active": false,
  "poller_target": null
}
```

### `GET /api/metrics/status`

Full metrics collection status.

**Response:**

```json
{
  "collector_connected": true,
  "clients_connected": 3,
  "poller": {
    "active": false,
    "target": null,
    "last_metrics": null
  }
}
```

### `GET /`

Service information and available endpoints.

**Response:**

```json
{
  "service": "Metrics Service",
  "version": "1.0.0",
  "description": "A reusable microservice for system metrics collection and relay",
  "endpoints": {
    "websocket_collector": "/ws/collector",
    "websocket_clients": "/ws/clients",
    "health": "/health",
    "health_detailed": "/api/health",
    "metrics_status": "/api/metrics/status"
  }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_PORT` | `9090` | Port to run the service on |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `TARGET_SERVICE_URL` | `` | Optional: URL of service to poll for metrics |
| `METRICS_ENDPOINT` | `/api/metrics/status` | Endpoint path on target service for polling |
| `POLL_INTERVAL_SECONDS` | `2` | Polling interval in seconds |

### Example Configuration

```bash
# Production settings
export METRICS_PORT=9090
export LOG_LEVEL=WARNING
export CORS_ORIGINS=https://dashboard.example.com,https://admin.example.com

# With optional polling enabled
export TARGET_SERVICE_URL=http://my-app:8080
export METRICS_ENDPOINT=/api/metrics
export POLL_INTERVAL_SECONDS=2
```
