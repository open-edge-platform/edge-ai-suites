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
  "clients_connected": 0
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
    "health_detailed": "/api/health"
  }
}
```