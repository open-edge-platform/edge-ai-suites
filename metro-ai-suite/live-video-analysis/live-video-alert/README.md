# Live Video Alert

Deploy AI-powered real-time alerting for live video streams with Intel® optimized Vision Language Models (VLMs).

## Quick Start

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-alert

# Set required environment variable
export RTSP_URL=rtsp://<camera-ip>:<port>/stream

# Start the application
docker compose up -d

# Access dashboard at http://localhost:9000
```

**Note**: First run downloads the VLM model (~2GB). Subsequent runs are instant.

## Learn More

- [Overview](docs/user-guide/overview.md) - Architecture and features
- [System Requirements](docs/user-guide/system-requirements.md) - Hardware and software requirements
- [Get Started](docs/user-guide/get-started.md) - Complete deployment guide
- [How to Build from Source](docs/user-guide/how-to-build-source.md) - Build instructions
- [API Reference](docs/user-guide/api-reference.md) - REST API documentation
