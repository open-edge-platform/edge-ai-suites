# Release Notes: Live Video Alert Agent

## Version 2026.2.0

**New**

- **Microservice architecture for action dispatch.** Alert action dispatch
  (tool execution, ADK agent reasoning, webhook/MQTT delivery) is now handled
  by the external `alert-agent-service` microservice, deployed as a sidecar
  container. This provides better separation of concerns, independent scaling,
  and reusability across different detection pipelines.
- **Simplified live-video-alert-agent.** The agent now focuses solely on video
  ingestion, VLM inference, and alert state management. Dependencies on
  `google-adk`, `litellm`, and `paho-mqtt` have been removed.
- **HTTP-based tool proxy.** The `/tools` API endpoints now proxy to the
  alert-agent-service, maintaining backward compatibility for dashboard and
  API consumers.

**Changed**

- `USE_ADK` environment variable removed — use `AGENT_MODE` on the
  `alert-agent-service` container instead.
- `LLM_*`, `WEBHOOK_*`, and `MQTT_*` environment variables moved from
  live-video-alert-agent to alert-agent-service.
- New environment variables: `ALERT_AGENT_SERVICE_URL`,
  `ALERT_AGENT_SERVICE_TIMEOUT`.
- Docker Compose now includes `alert-agent-service` as a required sidecar
  and an optional `mqtt` service.

## Version 2026.1.0

**June 17, 2026**

**New**

- **Google ADK agentic dispatch.** Alert actions are now driven by a
  [Google ADK](https://adk.dev/) `LlmAgent` that reasons over
  the available tools and selects the right ones at runtime.
- **Model Context Protocol (MCP) integration.** The agent can now connect to
  external MCP servers and expose their tools alongside built-in tools.
- **Per-alert tool argument overrides.** `AlertConfig` now accepts the
  `tool_arguments` field that supplies per-tool keyword-argument overrides.
- **Separate LLM OVMS service.** Includes the dedicated OVMS deployment for the
  ADK reasoning model and a service separate from the VLM inference.

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
