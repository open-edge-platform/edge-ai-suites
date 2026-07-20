# Live Video Alert Agent

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/live-video-analysis/live-video-alert-agent">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/live-video-analysis/live-video-alert-agent/README.md">
     Readme
  </a>
</div>
hide_directive-->

Deploy AI-powered video alerting using OpenVINO Vision Language Models to process RTSP streams,
generate real-time alerts from natural language prompts, and delegate automated action dispatch
to the alert-agent-service microservice.

## Use Cases

**Real-time Video Analytics**: Monitor security cameras, industrial equipment, or public spaces with AI-powered scene understanding and automatic alerting.

**Safety Monitoring**: Deploy prompts like "Is there a fire?" or "Is anyone wearing a safety vest?" to trigger immediate notifications via webhook or MQTT.

**Agentic Alert Response**: Use the alert-agent-service to handle ADK-powered tool reasoning and automatically select actions such as snapshots, webhooks, or MQTT notifications.

**Custom Alerts**: Use natural language to define what constitutes an alert without retraining a model.

## Key Features

**Dynamic Alert Prompts**: Define and modify alerts (prompts) in real-time through the UI or REST API without redeploying.

**Agentic Tool Dispatch**: When an alert fires, the live-video-alert-agent sends the action request to the external alert-agent-service, which performs ADK-powered or rule-based tool dispatch.

**Alert State Management**: Per-stream, per-alert cooldowns and consecutive-detection escalation suppress noise while ensuring persistent conditions trigger escalated responses.

**Built-in Action Tools**: The alert-agent-service provides `log_alert`, `capture_snapshot`, `trigger_webhook` (HMAC-signed), `publish_mqtt` (MQTTv5), and related MCP-managed tools.

**Concurrent Multi-Camera**: Each camera stream runs in its own independent asyncio task — slow or stalled cameras do not block others.

**Real-time Event Broadcasting**: SSE delivers analysis results and `alert_action` events instantly to the dashboard with low latency.

**Observability Endpoints**: `/health`, `/ready`, `/metrics` for liveness probes, readiness checks, and CPU/memory monitoring.

**Intel® Hardware Optimized**: Designed for high-performance inference on Intel® CPUs and GPUs via OpenVINO.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
how-it-works.md
api-reference.md
known-issues.md
Release Notes <release-notes.md>

:::
hide_directive-->
