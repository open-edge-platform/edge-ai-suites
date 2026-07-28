# Release Notes: Federal And Aerospace Suite

<!--## Version 2026.2.0-->

<!--date TBD-->

## Version 2026.1.1

Initial release (preview) version of the application and the Infrastructure blueprint.
The application is optimized for AI inference on portable devices, focusing on SWaP-C
compliance (Size, Weight, Power, and Cost).

**New**

The application introduces the following features:

- Deployment on top of [Edge Node Infrastructure Blueprint](https://docs.openedgeplatform.intel.com/main/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/index.html), an edge computing platform that enables hardware acceleration capabilities
- Text and audio modality support through Conversational Agent exposed via Chat UI that is backed by LLM served by OpenVINO Model Server
- Audio modality support through Speech To Text Service (Whisper)
- Visual modality support through [Visual Pipeline and Platform Evaluation Tool](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).
- Insight into application and platform metrics through the Observability Dashboard

**Known issues and limitations**

- When the virtual function is used for GPU, metrics in the Visual Pipeline and Platform Evaluation Tool are not available. The metrics are exposed correctly when the physical function is used.
- The version of Visual Pipeline and Platform Evaluation Tool used in the Handheld Multi-Modal Application does not fully support pipelines that utilize Hugging Face models requiring access approval and downloading via an access token. As a result the Video Summarization VLM pipeline is not available in the preview release.
- Ubuntu ISO file download status is not known on build failure.
- Starting too many pipelines may lead to system overload, which results in "Pipeline run error" message in ViPPET.
- After long conversation in OpenWeb UI, `OpenVINO/Phi-3.5-mini-instruct-int4-ov` model can start responding in gibberish output instead of logical language. To fix issue, start a new session in OpenWeb UI.
- It is not possible to select historical metrics in Grafana despite having a timepicker. Dashboards only show live metrics that are stored in buffer, which can contains metrics from last ~5 minutes.
- Grafana metric for Whisper only appear after whole file is processed instead of appearing in realtime. Whisper itself is working as expected and performs speech-to-text in realtime, which is visible on Whisper's page.
