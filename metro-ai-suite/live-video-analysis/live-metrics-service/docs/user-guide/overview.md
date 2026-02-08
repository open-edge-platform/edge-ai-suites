# Overview

The Metrics Service provides a decoupled solution for collecting, relaying, and visualizing system metrics in real-time. It acts as a WebSocket relay between metrics collectors (like Telegraf) and dashboard clients, enabling live visualization of CPU, memory, GPU, and other system metrics.

## Key Benefits

- Fully decoupled from application services
- Deploy once, use with any frontend
- Horizontal scalability for multiple clients
- Works with standard Telegraf collectors

## Architecture

### Data Flow

1. **Collector → Service**: Telegraf sends metrics as JSON via WebSocket to `/ws/collector`
2. **Service Processing**: Metrics are wrapped in `{"metrics": [...]}` format if needed
3. **Service → Clients**: Metrics are broadcast to all connected clients on `/ws/clients`

## Features

| Feature | Description |
|---------|-------------|
| **WebSocket Relay** | Receives metrics from collectors and broadcasts to clients in real-time |
| **Multi-Client Support** | Unlimited concurrent client connections with automatic cleanup |
| **Single Collector Lock** | Ensures only one collector can connect at a time for data integrity |
| **Health Monitoring** | Built-in health and status endpoints for orchestration |
| **CORS Support** | Configurable CORS for cross-origin dashboard access |
| **Container-Ready** | Optimized Docker image with non-root user |
