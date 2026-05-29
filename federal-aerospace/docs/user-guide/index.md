# Handheld Multi-Modal

Full-stack AI inference and observability platform for handheld deployment scenarios, optimized for Intel edge hardware.

Combines an LLM inference server, a speech-to-text service, a chat UI, and a metrics/dashboarding stack into a single composable solution. Designed to run alongside the [Visual Pipeline and Platform Evaluation Tool (vippet)](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/tools/visual-pipeline-and-platform-evaluation-tool), sharing its Docker network.

Consists of 2 parts:

- Preparation of power-optimized OS that supports hardware acceleration capabilities (GPU, NPU, SR-IOV, etc.) for modern applications
- Deployment of local LLM inference server, a speech-to-text service, a chat UI, and a metrics/dashboarding stack into a single composable solution

<!--hide_directive
:::{toctree}
:hidden:

OS preparation <os.md>
Handheld Multi-Modal <hmm.md>
release-notes <release-notes.md>

:::
hide_directive-->
