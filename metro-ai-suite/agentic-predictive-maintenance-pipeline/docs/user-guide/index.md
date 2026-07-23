# Agentic Predictive Maintenance

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-libraries/tree/main/sample-applications/agentic-predictive-maintenance">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/agentic-predictive-maintenance/README.md">
     Readme
  </a>
</div>
hide_directive-->

The Agentic Predictive Maintenance (APM) blueprint is a configuration-driven, multi-agent sample
application for industrial defect detection on Intel® edge hardware. It processes live or recorded
video to detect defects, stores detection data, and uses a LangGraph framework-based multi-agent pipeline to
analyze findings and generate structured maintenance tickets without any code changes between use
cases.

You can extend the application to new industrial inspection scenarios by editing
configuration files.

## Key Capabilities

- **Real-time defect detection**: DL Streamer runs a YOLO model against video input and publishes
  detection events over Message Queuing Telemetry Transport (MQTT).
- **Multi-agent reasoning**: A LangGraph pipeline with four specialized agents (Policy, Analysis,
  Evidence, Ticketing) processes detections and produces actionable maintenance tickets.
- **Two operating modes**: Run fully with a Large Language Model (LLM) for AI-generated analysis,
  or in the fallback mode with rule-based logic when no GPU or LLM service is available.
- **Configuration-driven extensibility**: Adapt the blueprint to any defect detection use case by
  editing four configuration files. No code changes are required.
- **Built-in observability**: Both the storage and agent services expose Prometheus metrics.

## Quick Start

- **Get Started**
  - [Get Started](./get-started.md): Set up, configure, and run the application.
  - [System Requirements](./get-started/system-requirements.md): See hardware and software prerequisites.

- **How It Works**
  - [How It Works](./how-it-works.md): End-to-end data flow and agent pipeline details.

- **Development**
  - [Build from Source](./build-from-source.md): Build the application images from source code.

- **API Reference**
  - [API Reference](./api-reference.md): Representational State Transfer (REST) API endpoints for
    the storage and agent services.

- **Release Notes**
  - [Release Notes](./release-notes.md): Latest updates and changes.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
build-from-source
api-reference
troubleshooting
release-notes
:::
hide_directive-->
