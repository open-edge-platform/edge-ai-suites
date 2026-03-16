# Release Notes: Live Video Alert Agent

## Version 1.0.0

**April 01, 2026**

Live Video Alert Agent is a new sample "agentic application" that accepts live camera input
and enables monitoring for up to four events on a single camera stream. Alerts are raised when
the events occur, based on user-configured prompts for a VLM.

A rich UI is provided to configure various features of the application, such as the prompt
capturing the event to be monitored, and provides a dashboard view of the compute and memory
usage.

**New**

- Initial release of Live Video Alert.
- Live-metrics-service for CPU, GPU, and memory utilization integrated directly in the dashboard.
- OVMS GPU support.
- RTSP video ingestion with VLM inference (Phi-3.5-Vision, InternVL2-2B).
- Natural language alert configuration (max 4 alerts per stream).
- Real-time SSE event broadcasting and interactive dashboard.
- Configurable CPU/GPU inference via TARGET_DEVICE environment variable.

**Known Issues**

- Helm support is not available in this version.
