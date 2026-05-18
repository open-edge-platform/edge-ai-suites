# Release Notes: Live Video Alert Agent

## Version 2026.1.0-rc1
**May 13, 2026**

- **Google ADK agentic dispatch.** Alert actions are now driven by a
  [Google ADK](https://google.github.io/adk-docs/) `LlmAgent` that reasons over
  the available tools and selects the right ones at runtime.
- **Model Context Protocol (MCP) integration.** The agent can now connect to
  external MCP servers and expose their tools alongside built-in tools.
- **Per-alert tool argument overrides.** `AlertConfig` now accepts a
  `tool_arguments` field that supplies per-tool keyword-argument overrides.
- **Separate LLM OVMS service.** Includes a dedicated OVMS deployment for the ADK reasoning model and separate from the VLM inference service.

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
- Helm chart for Kubernetes deployment.
