# Handheld Multi-Modal Application

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.1.0/federal-aerospace/apps/handheld-multi-modal">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/federal-aerospace/apps/handheld-multi-modal/README.md">
     Readme
  </a>
  <a class="icon_download" href="https://github.com/open-edge-platform/edge-ai-suites/releases/download/2026.1/handheld-multi-modal.zip">
     Download Package
  </a>
</div>
hide_directive-->

The Handheld Multi-Modal application is a full-stack AI inference and observability software
collection consisting of both single- and multi-modal components that are optimized for
Intel® edge hardware in handheld deployment scenarios.

This composite application combines a conversational agent exposed via Chat UI that is backed by
a LLM inference server, a speech-to-text service and
[Visual Pipeline and Platform Evaluation Tool](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).
All components of the composite application share the visual pipeline solution's Docker network.

Deployment of the the full solution consists of two main stages:

1. Setting up [Edge Node Infrastructure Blueprint](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/index.html) which is an edge computing platform that enables hardware acceleration capabilities,
2. Installation of the composite Handheld Multi-Modal Application that makes use of the hardware accellerated compute platform.

## Components of the Handheld Multi-Modal Application

The application combines a conversational agent (Chat UI) exposed as Open WebUI component
backed by LLM model served through the OpenVINO Model Server platform, a speech-to-text
transcription functionality realized by the Whisper model, and observability dashboard
exposed via Grafana dashboard for a live view of platform utilization and application metrics.

### Visual Pipeline and Platform Evaluation Tool

The Visual Pipeline and Platform Evaluation Tool simplifies hardware selection for AI workloads by enabling
configuration of workload parameters, performance benchmarking, and analysis of key metrics such as throughput,
CPU usage, and GPU usage. With its intuitive interface, the tool provides actionable insights that support
optimized hardware selection and performance tuning.

For more information, see [ViPPET documentation](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).

<!-- ViPPET 2026.0 is used here on purpose -->

> **Notice:**
> The version of Visual Pipeline and Platform Evaluation Tool used in the Handheld
  Multi-Modal Application does not fully support pipelines that utilize
  [Hugging Face](https://huggingface.co/) models, requiring access approval and downloading
  via an access token. As a result the Video Summarization VLM pipeline is not available in
  the preview release.

### Speech To Text (Whisper Model)

This component is responsible for speech to text functionality and uses Whisper model.
Whisper is a general-purpose speech recognition model. It is trained on a large dataset of
diverse audio and is also a multitasking model that can perform multilingual speech recognition,
speech translation, and language identification.

For more information, see [Whisper documentation](https://github.com/openai/whisper).

### Web UI

**Open WebUI** is an [extensible](https://docs.openwebui.com/features/extensibility/plugin),
feature-rich, and user-friendly self-hosted AI platform designed to operate entirely offline.
It supports various  runners, such as **Ollama** and **OpenAI-compatible APIs**, with
a built-in inference engine for RAG, making it a powerful AI deployment solution.

For more information, see [Web UI documentation](https://github.com/open-webui/open-webui).

### Observability

The application includes [Grafana Open Source (OSS)](https://grafana.com/docs/grafana/v13.0/), a data visualization and analytics tool. A Grafana Dashboard is
supplied that aggregates and presents metrics from the components of the application
and from the underlying platform. Metrics are streamed over websocket to Grafana
for a live, ephemeral on-device view. Additionally, a Prometheus endpoint is exposed at
`localhost:9273/metrics` address, from which data can be scraped for
long-term persistence.

## Composite Application installation

Proceed to [Application Deployment](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-suites/ai-suite-federal-and-aerospace/handheld-multi-modal-application/deploy-applications.html).
and follow the guide to install Handheld Multi-Modal Application.

<!--hide_directive
:::{toctree}
:hidden:

Application Deployment <deploy-applications.md>

:::
hide_directive-->
