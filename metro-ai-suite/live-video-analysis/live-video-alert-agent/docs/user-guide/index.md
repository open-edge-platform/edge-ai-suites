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
generate real-time alerts from natural language prompts, and respond automatically through
a configurable agentic action pipeline.

## Use Cases

**Real-time Video Analytics**: Monitor security cameras, industrial equipment, or public spaces with AI-powered scene understanding and automatic alerting.

**Safety Monitoring**: Deploy prompts like "Is there a fire?" or "Is anyone wearing a safety vest?" to trigger immediate notifications via webhook or MQTT.

**Agentic Alert Response**: Use Google ADK or a local LLM to reason about alert severity and automatically select which tools to invoke — snapshot, webhook, or MQTT.

**Custom Alerts**: Use natural language to define what constitutes an alert without retraining a model.

## Key Features

**Dynamic Alert Prompts**: Define and modify alerts (prompts) in real-time through the UI or REST API without redeploying.

**Agentic Tool Dispatch**: When an alert fires, an action agent decides which tools to invoke — powered by Google ADK, an OVMS-hosted LLM, or deterministic rule-based execution.

**Alert State Management**: Per-stream, per-alert cooldowns and consecutive-detection escalation suppress noise while ensuring persistent conditions trigger escalated responses.

**Built-in Action Tools**: `log_alert`, `capture_snapshot`, `trigger_webhook` (HMAC-signed), `publish_mqtt` (MQTTv5).

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
