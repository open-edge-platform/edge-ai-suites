<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.0.0/metro-ai-suite/live-video-analysis/live-video-alert-agent">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.0.0/metro-ai-suite/live-video-analysis/live-video-alert-agent/README.md">
     Readme
  </a>
</div>
hide_directive-->

# Live Video Alert Agent

Deploy AI-powered video alerting using OpenVINO Vision Language Models to process RTSP streams,
generate real-time alerts from natural language prompts, and monitor them on a unified dashboard.

## Use Cases

**Real-time Video Analytics**: Monitor security cameras, industrial equipment, or public spaces with AI-powered scene understanding and automatic alerting.

**Safety Monitoring**: Deploy prompts like "Is there a fire?" or "Is anyone wearing a safety vest?" to trigger immediate visual notifications.

**Custom Alerts**: Use natural language to define what constitutes an alert without retraining a model.

## Key Features

**Dynamic Alert Prompts**: Define and modify "Alerts" (prompts) in real-time through the UI without redeploying.

**Real-time Event Broadcasting**: Server-Sent Events (SSE) deliver instant alerts to the dashboard with low latency.

**Modular Architecture**: Decoupled ingestion, analysis, and event broadcasting for scalability.

**Intel® Hardware Optimized**: Designed for high-performance inference on Intel® CPUs and GPUs via OpenVINO.

<!--hide_directive
:::{toctree}
:hidden:

get-started
system-requirements
how-to-build-source
how-it-works
api-reference
known-issues
Release Notes <release-notes.md>

:::
hide_directive-->
