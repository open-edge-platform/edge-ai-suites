# Release Notes

## Current Release: 1.0.0-rc1

**Release Date**: 17 Feb 2026

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

### Known Issues
- Helm is not supported
- This release includes only limited testing on EMT‑S and EMT‑D, some behaviors may not yet be fully validated across all scenarios.
