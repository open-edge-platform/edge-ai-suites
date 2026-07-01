# Release Notes: Handheld Multi-Modal Application

## Version 2026.1

Initial release (preview) version of the application. The application is optimized for AI inference on portable devices, focusing on SWaP-C compliance (Size, Weight, Power, and Cost).

**New**

The application introduces the following features:

- Deployment on top of [Edge Node Infrastructure Blueprint](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/index.html), an edge computing platform that enables hardware acceleration capabilities
- Text and audio modality support through Conversational Agent exposed via Chat UI that is backed by LLM served by OpenVINO Model Server
- Audio modality support through Speech To Text Service (Whisper)
- Visual modality support through [Visual Pipeline and Platform Evaluation Tool](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).
- Insight into application and platform metrics through the Observability Dashboard

**Known issues and limitations**

- When the virtual function is used for GPU, metrics in the Visual Pipeline and Platform Evaluation Tool are not available. The metrics are exposed correctly when the physical function is used.
- The version of Visual Pipeline and Platform Evaluation Tool used in the Handheld Multi-Modal Application does not fully support pipelines that utilize Hugging Face models requiring access approval and downloading via an access token. As a result the Video Summarization VLM pipeline is not available in the preview release.
- Incorrect power readings may occur on images built with 6.18-intel kernel, resulting in spurious analytic data. This is a known issue that is currently undergoing a detailed root-cause analysis.
