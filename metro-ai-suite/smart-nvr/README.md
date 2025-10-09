# Smart NVR: GenAI-Enabled Network Video Recorder

The Smart NVR is a next-generation network video recorder that integrates GenAI-powered vision analytics to deliver intelligent, real-time insights from video streams. By processing and analyzing video data directly at the edge, it enables advanced event detection, summarization, and automation while reducing bandwidth and storage requirements. This transformation empowers organizations to extract greater value from their existing video infrastructure and respond rapidly to critical situations.

## Documentation

- **Overview**
  - [Overview](docs/user-guide/Overview.md): A high-level introduction.
  - [Overview Architecture](./docs/user-guide/Overview.md#how-it-works): Highlevel architecture.

- **Getting Started**
  - [Get Started](docs/user-guide/get-started.md): Step-by-step guide to get started with the sample application.
  - [System Requirements](docs/user-guide/system-requirements.md): Hardware and software requirements for running the sample application.
  - [How to Use the Application](./docs/user-guide/how-to-use-application.md): Explore the application's features and verify its functionality.

- **Deployment**
  - [How to Build from Source](docs/user-guide/how-to-build-from-source.md): Instructions for building from source code.

- **Advanced Integrations**
  - [Intel Scenescape Integration](docs/user-guide/scenescape-integration.md): Complete guide for integrating with Intel Scenescape for traffic analytics and vehicle counting.

- **API Reference**
  - [API Reference](docs/user-guide/api-reference.md): Comprehensive reference for the available REST API endpoints.

- **Release Notes**
  - [Release Notes](docs/user-guide/release-notes.md): Information on the latest updates, improvements, and bug fixes.

## Quick Start: Intel Scenescape Integration

Smart NVR supports integration with Intel Scenescape for advanced traffic analytics and vehicle counting capabilities.

### Enable Scenescape Integration

```bash
# Set environment variable
export NVR_SCENESCAPE=true

# Configure MQTT credentials  
export SCENESCAPE_MQTT_USER="your_username"
export SCENESCAPE_MQTT_PASSWORD="your_password"

# Restart application
./setup.sh restart
```

### Key Features with Scenescape

- **Real-time Vehicle Counting**: Monitor traffic flow with live vehicle counts
- **Threshold-based Rules**: Create rules that trigger when vehicle count exceeds thresholds  
- **Traffic Analytics**: Advanced analytics from Intel Scenescape platform
- **Dual Source Support**: Use both Frigate and Scenescape sources simultaneously

### User Interface Changes

**With Scenescape Enabled:**
- Source dropdown includes both "frigate" and "scenescape" options
- Vehicle Count field appears when scenescape is selected
- Rules table includes Vehicle Count column

**With Scenescape Disabled:**  
- Source dropdown shows only "frigate" option
- No vehicle count configuration
- Standard Frigate-only interface

📖 **[Complete Scenescape Integration Guide →](docs/user-guide/scenescape-integration.md)**