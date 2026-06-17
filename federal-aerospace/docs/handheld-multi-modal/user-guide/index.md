# Handheld Multi-Modal Application

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.1.0/federal-aerospace/apps/handheld-multi-modal">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/federal-aerospace/apps/handheld-multi-modal/README.md">
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
[Visual Pipeline and Platform Evaluation Tool](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html),
sharing its Docker network.

It assumes two main stages:

1. Preparation of power-optimized OS that supports hardware acceleration, for example,
   GPU or NPU, as well as Single Root I/O Virtualization (SR-IOV) for modern applications.
2. Deployment of the composition pieces, such as a local LLM inference server.

## Handheld Multi-Modal Components

The application combines LLM inference capability served through the OpenVINO Model Server
platform, speech-to-text transcription through the Whisper service, a chat UI through the
Open WebUI software, and metrics information through the Grafana dashboard.

### Visual Pipeline and Platform Evaluation Tool

The Visual Pipeline and Platform Evaluation Tool simplifies hardware selection for AI workloads by enabling
configuration of workload parameters, performance benchmarking, and analysis of key metrics such as throughput,
CPU usage, and GPU usage. With its intuitive interface, the tool provides actionable insights that support
optimized hardware selection and performance tuning.

For more information, see [ViPPET documentation](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).

### Whisper Model

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

<!--hide_directive
:::{toctree}
:hidden:

Application Deployment <deploy-applications.md>

:::
hide_directive-->
