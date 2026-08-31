# Release Notes: Agentic Predictive Maintenance

## Version 2026.2.0

**Release Date**: September 9, 2026

**Features**:

- **Initial release** of the Agentic Predictive Maintenance (APM) blueprint.
- Configuration-driven multi-agent pipeline using LangGraph. Adapt to any defect detection use case
  by editing four configuration files — no code changes required.
- Four-agent reasoning pipeline: Policy Agent, Analysis Agent, Evidence Agent, and Ticketing Agent
  run sequentially to analyze detections and generate structured maintenance tickets. The reasoning
  agent (`apm-agent`) is not built from this repo — it is an external image (Intel EAL's
  `agent-quality-handler` microservice) pulled via `docker/compose.agents.yaml`. See the
  [agent-service integration guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/agent-quality-handler/docs/user-guide/agent-service-integration-guide.md) for its contract.
- Two operating modes: Large Language Model (LLM) mode for AI-generated analysis (using OpenVINO
  Model Server) and fallback mode for rule-based operation without an LLM service.
- Real-time video inference via Deep Learning Streamer (DL Streamer) with YOLO-based object detection; DL Streamer publishes
  detection events over Message Queuing Telemetry Transport (MQTT).
- SQLite database-backed storage service with Representational State Transfer (REST) API for querying
  detections and statistics.
- Web dashboard (React) with live detection feed, run history, and ticket viewer.
- The storage service and agent service both expose Prometheus metrics.
- Reference use case: `pipeline-defect-detection` with four defect classes — Rupture, Deformation,
  Disconnect, and Obstacle.
- **Interactive Chat (Ask & Analyze)**: conversational interface in the web dashboard that lets
  operators query maintenance analysis, detection evidence, and pipeline data using natural language.
  Answers are generated from available pipeline data via the LLM service.
- Data preparation script for downloading and building sample video from a public Kaggle dataset.
- On-demand "Run Pipeline" trigger: one full detect-then-reason cycle per click — the DL Streamer
  pipeline runs once over the (finite) source video, then the agent pipeline reasons over exactly
  the detections that the run produced (an `id`-based window). Only one run may be in flight at a time;
  the agent-service rejects concurrent triggers with `409`. Live and continuous background detection
  is planned for a future iteration.

**Hardware Used for Validation**:

- 5th Gen Intel® Xeon® processors (CPU-only)
- Intel® Core™ Ultra processors with Intel® Arc™ GPU (LLM mode)

**Known Limitations**:

- Neural Processing Unit (NPU) inference support for the LLM service is
  experimental and is not validated for all model and configuration combinations.
- Only the `pipeline-defect-detection` use case is provided as a reference
  configuration. Additional use cases require manual configuration file setup.
- This release does not include a Helm chart for Kubernetes deployment.
