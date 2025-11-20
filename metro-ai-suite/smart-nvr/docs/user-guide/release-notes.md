# Release Notes

## Current Release

**Version**: 1.2.1 \
**Release Date**: 30 October 2025

**New Features**

- Continuous Video Streaming: Introduced support for uninterrupted video streaming based on user-selected cameras.
- Helm Chart Support: Deployment via Helm charts is now supported, simplifying installation and configuration.
- Rules Engine Integration: Enabled communication between the rules engine and Scenescape, demonstrated using the Smart Intersection RI integration.
- Unit Testing: Added comprehensive unit test cases to improve reliability and maintainability.

**Known Issues**

- Scenescape Integration Limitation: Scenescape integration is currently not supported when deploying via Helm charts.
- EMF and EMT are not supported yet.
- The **AI-Powered Event Viewer** feature relies on Frigate GenAI features, which may exhibit instability or bugs, impacting event data processing reliability.

## Previous Release

**Version**: 1.2.0 \
**Release Date**: 04 August 2025

**Features**:

- This is an incremental release on top of RC1 providing fixes for issues found on RC1. The notes provided under RC1 apply for this incremental release too.
- Issues fixed are listed below:
  - Updated docker images to public registry.
  - Updated README to pull the image from remote registry.

## Previous releases

**Version**: RC1 \
**Release Date**: 14 July 2025

**Features**:

- Smart NVR backend and frontend based on the single docker image
- Gradio based UI for selecting the use case
- Docker compose based deployment for the E2E application
- Auto Routing of the NVR events
- Routing of the events based on the timestamp
- [Experimental] Showcasing Using NVR's Event routing capabilities to OEP VLM microservice.

**HW used for validation**:

- Intel® Xeon® 5 + Intel® Arc&trade; B580 GPU

**Known Issues/Limitations**:

- EMF and EMT are not supported yet.
- Users are required to build the images and use the sample application. Docker images are not available yet on public registries (pending approvals).
- Helm charts for the application are not supported in this release.
- The **AI-Powered Event Viewer** feature relies on Frigate GenAI features, which may exhibit instability or bugs, impacting event data processing reliability.