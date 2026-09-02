# Surgical Instrument Sample App

<!--hide_directive
::::{container} component_header_row
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/health-and-life-sciences-ai-suite/surgical_instrument">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/health-and-life-sciences-ai-suite/surgical_instrument/README.md">
     Readme
  </a>
</div>
hide_directive-->

> Note:
> This application is for **reference and evaluation purposes only**. It is
  **not intended for direct use in clinical or diagnostic environments** and is not
  validated for such a purpose.

<!--hide_directive :::: hide_directive-->

The app demonstrates how Intel hardware acceleration (CPU / Intel iGPU / Intel NPU) may
be applied through OpenVINO to AI-based real-time polyp detection in a video of an endoscopic
procedure. It is packaged as a Docker Compose workload with a decoupled capture / inference /
display architecture, so the displayed video stays smooth regardless of inference speed.

Supported inputs:

- Basler industrial camera (via `pypylon`)
- USB / V4L2 webcam
- Video file (for demos and benchmarking)

Display path:

- OpenGL vsync presenter with `cv2` and headless fallback
- Optional fullscreen direct-scanout for low latency
- Optional camera trigger modes (`software`, `vsync`) for low photon-to-pixel
  latency

How to start:

- See [Model Preparation](./get-started/model-preparation.md) if you do not
  already have a trained OpenVINO IR under
  `models/yolo11n_polyp/best_openvino_model/`. Skip this page when pulling a
  prebuilt model from the registry.
- See [Get Started](./get-started.md) for a step-by-step deployment guide.
- See [Runtime Configuration](./runtime-configuration.md) for every knob and
  CLI option exposed by the app.
- See [Troubleshooting](./troubleshooting.md) for common issues.
- See [Release Notes](./release-notes.md) for version history.




<!--hide_directive
:::{toctree}
:hidden:

Get Started <get-started.md>
Runtime Configuration <./runtime-configuration.md>
Troubleshooting <./troubleshooting.md>
Release Notes <./release-notes.md>
:::
hide_directive-->
