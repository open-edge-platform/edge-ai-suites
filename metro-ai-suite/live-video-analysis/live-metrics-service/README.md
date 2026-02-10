# Metrics Service

A reusable, containerized microservice for system metrics collection and real-time streaming.

## Overview

The Metrics Service provides a decoupled solution for collecting, relaying, and visualizing system metrics in real-time. It acts as a WebSocket relay between metrics collectors (like Telegraf) and dashboard clients, enabling live visualization of CPU, memory, GPU, and other system metrics.

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and customize as needed:

```bash
cp .env.example .env
```

Edit `.env` to configure:
- `METRICS_PORT` - Service port (default: 9090)
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `CORS_ORIGINS` - CORS allowed origins (default: *)

```bash
export REGISTRY="intel/"
export TAG="1.0.0-rc.0"
docker compose up
```

### 2. Verify the Service

```bash
curl http://localhost:9090/health
# Response: {"status": "healthy"}
```

## Documentation

Comprehensive documentation is available in the [user-guide](docs/user-guide/) directory:

- [Overview](docs/user-guide/overview.md) - Architecture, features, and data flow
- [Get Started](docs/user-guide/get-started.md) - Quick start guide and integration examples
- [API Reference](docs/user-guide/api-reference.md) - Complete WebSocket and REST API documentation
- [Known Issues](docs/user-guide/known-issues.md) - Troubleshooting and common issues
- [Release Notes](docs/user-guide/release-notes.md) - Version history and changes

## Support

For issues, questions, or contributions, please refer to the [Known Issues](docs/user-guide/known-issues.md) documentation.

