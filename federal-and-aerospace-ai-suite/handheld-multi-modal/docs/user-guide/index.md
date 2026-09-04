# Handheld (Soldier System) Blueprint

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/federal-and-aerospace-ai-suite/handheld-multi-modal">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/handheld-multi-modal/README.md">
     Readme
  </a>
  <a class="icon_download" href="https://github.com/open-edge-platform/edge-ai-suites/releases/download/2026.1/handheld-multi-modal.zip">
     Download Package
  </a>
</div>
hide_directive-->

The Handheld Blueprint is a full-stack AI inference and observability software
collection consisting of both single- and multi-modal components that are optimized for
Intel® edge hardware in handheld deployment scenarios.

This composite application combines a conversational agent exposed via Chat UI that is backed by
a LLM inference server, a speech-to-text service and
[Visual Pipeline and Platform Evaluation Tool](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).
All components of the composite application share the visual pipeline solution's Docker network.

The Handheld Multi-Modal application is deployed on top of the
[Edge Node Infrastructure software](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/index.html) - an edge computing platform, which enables hardware acceleration capabilities.

## Deployment and Usage

Follow these steps to deploy the Handheld (Soldier System) Blueprint:

1. [Infrastructure Setup](infrastructure-setup.md) — Build the OS image, flash it to a bootable USB, and validate the provisioned platform.
2. [Install OEP SDKs](install-oep-sdks.md) — Verify hardware accelerators and install the OEP Vision AI SDK on the provisioned target.
3. [Install Handheld Multi-Modal Application](deploy-applications.md) — Download and deploy the composite application stack.
4. [Access Application User Interface](access-application.md) — Connect to the application endpoints and explore each component.
5. [Benchmarks](benchmarks.md) — Use the bundled ViPPET tool to benchmark AI pipelines across available hardware.

## Components

The Handheld application combines a conversational agent (Chat UI) exposed as Open WebUI component
backed by LLM model served through the OpenVINO Model Server platform, a speech-to-text
transcription functionality realized by the Whisper model, and observability dashboard
exposed via Grafana dashboard for a live view of platform utilization and application metrics.

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
It supports various  runners, such as **Ollama** and **OpenAI-compatible APIs**, with
a built-in inference engine for RAG, making it a powerful AI deployment solution.

For more information, see [Web UI documentation](https://github.com/open-webui/open-webui).

### Observability

The application includes [Grafana Open Source (OSS)](https://grafana.com/docs/grafana/latest/), a data visualization and analytics tool. A Grafana Dashboard is
supplied that aggregates and presents metrics from the components of the application
and from the underlying platform. Metrics are streamed over websocket to Grafana
for a live, ephemeral on-device view. Additionally, a Prometheus endpoint is exposed at
`localhost:9273/metrics` address, from which data can be scraped for
long-term persistence.

## AI Playground

AI Playground is an optional open source generative AI application suite for offline AI chat,
code assistance, document search, image analysis, and image and video generation, running on
the same Edge Node Infrastructure software platform. See the
[AI Playground — FedAero Setup Guide](ai-playground.md) for installation and setup steps.

<!--hide_directive
:::{toctree}
:hidden:

Infrastructure Setup <infrastructure-setup.md>
Install OEP SDKs <install-oep-sdks.md>
Install Handheld Multi-Modal Application <deploy-applications.md>
Access Application User Interface <access-application.md>
Benchmarks <benchmarks.md>
AI Playground <ai-playground.md>

:::
hide_directive-->
