# Handheld Multi-Modal Application

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/federal-aerospace/apps/handheld-multi-modal">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-aerospace/apps/handheld-multi-modal/README.md">
     Readme
  </a>
  <a class="icon_download" href="https://github.com/open-edge-platform/edge-ai-suites/releases/download/v2026.1.0/handheld-multi-modal.zip">
     Download Package
  </a>
</div>
hide_directive-->

The Handheld Multi-Modal application is a full-stack AI inference and observability software
collection optimized for Intel® edge hardware in handheld deployment scenarios.

The collection combines an LLM inference server, a speech-to-text service, a chat UI, and a
metrics or dashboarding stack into a single composable solution. It runs alongside the
[Visual Pipeline and Platform Evaluation Tool](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html),
sharing its Docker network.

It assumes two main stages:

1. Preparation of power-optimized OS that supports hardware acceleration, for example,
   GPU or NPU, as well as Single Root I/O Virtualization (SR-IOV) for modern applications.
2. Deployment of the composition pieces, such as a local LLM inference server.

## Handheld Multi-Modal Application Components

The application combines LLM inference capability served through the OpenVINO Model Server
platform, speech-to-text transcription through the Whisper service, a chat UI through the
Open WebUI software, and metrics information through the Grafana dashboard.

### Visual Pipeline and Platform Evaluation Tool

The Visual Pipeline and Platform Evaluation Tool simplifies hardware selection for AI workloads by enabling
configuration of workload parameters, performance benchmarking, and analysis of key metrics such as throughput,
CPU usage, and GPU usage. With its intuitive interface, the tool provides actionable insights that support
optimized hardware selection and performance tuning.

For more information, see [ViPPET documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).

### Speech To Text (Whisper Model)

This component is responsible for speech to text functionality and uses Whisper model.
Whisper is a general-purpose speech recognition model. It is trained on a large dataset of
diverse audio and is also a multitasking model that can perform multilingual speech recognition,
speech translation, and language identification.

For more information, see [Whisper documentation](https://github.com/openai/whisper).

### Web UI

**Open WebUI** is an [extensible](https://docs.openwebui.com/features/extensibility/plugin),
feature-rich, and user-friendly self-hosted AI platform designed to operate entirely offline.
It supports various LLM runners, such as **Ollama** and **OpenAI-compatible APIs**, with
a built-in inference engine for RAG, making it a powerful AI deployment solution.

For more information, see [Web UI documentation](https://github.com/open-webui/open-webui).

### Observability

The application includes [Grafana Open Source (OSS)](https://grafana.com/docs/grafana/v13.0/)
which is an open source data visualization and analytics software. A Grafana Dashboard is
supplied that aggregates and presents metrics from the components of the application
and from the underlying platform. The metrics are streamed via websocket to Grafana
for on-device live ephemeral view. Additionally a Prometheus endpoint is exposed at
`https://localhost:9273/metrics` address that can be scraped the data intended for
long-term persistence if needed.

<!--hide_directive
:::{toctree}
:hidden:

Application Deployment <deploy-applications.md>

:::
hide_directive-->
