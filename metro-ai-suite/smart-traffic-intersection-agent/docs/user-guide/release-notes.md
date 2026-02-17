# Release Notes

## Current Release: 1.0.0

**Release Date**: 2025-08-19

### Features

- **Real-time Traffic Analysis**: Comprehensive directional traffic density monitoring with MQTT integration
- **VLM Integration**: Vision Language Model (VLM)-powered traffic scene analysis with sustained traffic detection
- **Sliding Window Analysis**: 15-second sliding window with 3-second sustained threshold for accurate traffic state detection
- **Camera Image Management**: Intelligent camera image retention and coordination between API and VLM services
- **RESTful API**: Complete HTTP API for traffic summaries, intersection monitoring, and VLM analysis retrieval

### Improvements

- **Concurrency Control**: Semaphore-based VLM worker management for optimal resource utilization
- **Image Retention Logic**: Camera images persist with VLM analysis for consistent data correlation
- **Enhanced Error Handling**: Comprehensive error management across MQTT, VLM, and image services
- **Setup Script Enhancements**: Added `--build` option for building service images without starting containers

### Technical Specifications

- **Supported Languages**: Python programming version 3.10 or higher
- **Architecture**: Microservice with Docker containerization
- **Dependencies**: FastAPI, MQTT client, aiohttp, and structlog
- **External Integrations**: MQTT brokers, VLM OpenVINO serving, and camera image streams