# Federal Aerospace Suite

AI-enabled applications and supporting components for aerospace and defense edge deployments.

## Applications

### Handheld Multi-Modal

Full-stack AI inference and observability platform for handheld scenarios. Combines LLM inference (OpenVINO Model Server), speech-to-text (Whisper), a chat UI (Open WebUI), and metrics dashboards (Grafana), running alongside the [Visual Pipeline and Platform Evaluation Tool (vippet)](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/tools/visual-pipeline-and-platform-evaluation-tool) for pipeline visualization.

See [`apps/handheld-multi-modal/`](apps/handheld-multi-modal/README.md).

### Deterministic Threat Detection

[Deterministic Threat Detection](apps/deterministic-threat-detection) : A sample application that showcases Time-Sensitive Networking (TSN) to enable deterministic, low-latency transmission of AI-processed video and sensor data alongside best-effort traffic on a shared network. [User Docs](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-aerospace/apps/deterministic-threat-detection/docs/user-guide/index.md)

## Components

| Directory                               | Description                                |
|-----------------------------------------|--------------------------------------------|
| `apps/handheld-multi-modal/`            | Handheld multi-modal application           |
| `apps/deterministic-threat-detection/`  | Deterministic threat detection application |
| `docs/`                                 | Documentation                              |
