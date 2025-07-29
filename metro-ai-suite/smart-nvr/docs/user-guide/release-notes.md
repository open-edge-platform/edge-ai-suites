# Release Notes


## Current Release
**Version**: RC1 
**Release Date**: 14 July 2025  

**Features**:

• Smart NVR backend and frontend based on the single docker image
• Gradio based UI for selecting the use case
• Docker compose based deployment for the E2E application
• Auto Routing of the NVR events
• Routing of the events based on the timestamp
• [Experimental] Showcasing Using NVR's Event routing capabilities to OEP VLM microservice. 

**HW used for validation**:
- Intel® Xeon® 5 + Intel® Arc&trade; B580 GPU

**Known Issues/Limitations**:
- EMF and EMT are not supported yet.
- Users are required to build the images and use the sample application. Docker images are not available yet on public registries (pending approvals).
- Helm charts for the application are not supported in this release.
- The **AI-Powered Event Viewer** feature relies on Frigate GenAI features, which may exhibit instability or bugs, impacting event data processing reliability.

## Previous releases

**Version**:  \
**Release Date**:  

- <Previous release notes>
