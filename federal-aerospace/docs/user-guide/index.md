# Handheld Multi-Modal Platform

Handheld multi-modal platform is a full-stack AI inference and observability platform for handheld deployment scenarios, optimized for Intel® edge hardware.

The platform combines an LLM inference server, a speech-to-text service, a chat UI, and a metrics or dashboarding stack into a single composable solution. The solution runs alongside the [Visual Pipeline and Platform Evaluation Tool (vippet)](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/tools/visual-pipeline-and-platform-evaluation-tool), sharing its Docker network.

The platform consists of two parts:

- Preparation of power-optimized OS that supports hardware acceleration capabilities, for example, GPU, NPU, and Single Root I/O Virtualization (SR-IOV) for modern applications
- Deployment of local LLM inference server, a speech-to-text service, a chat UI, and a metrics or dashboarding stack into a single composable solution

<!--hide_directive
:::{toctree}
:hidden:

OS Preparation <os.md>
Handheld Multi-Modal Applications and Deployment <hmm.md>
Release Notes <release-notes.md>

:::
hide_directive-->
