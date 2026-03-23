# Release Notes: Embodied Intelligence SDK

## Version 2026.0

Embodied Intelligence SDK v26.0 introduces π₀.₅ (Pi0.5) -
a Vision-Language-Action (VLA) model with open-world generalization. It is
developed by [Physical Intelligence](https://www.pi.website/blog/pi05) and
designed to serve as a "general-purpose AI brain" for diverse robotic hardware.
The model represents a significant progress in integrating advanced reasoning
with precise physical control capabilities.

**New**

- [OpenVINO](https://docs.openvino.ai) Integration: Enable Pi0.5
  pipeline policy with OpenVINO inference optimized on Intel integrated GPU
- Add a script for OpenVINO model conversion.
- [Aloha](https://tonyzhaozh.github.io/aloha/) Pipeline Support: Include example
  implementation for both simulator and real robot environments.
- Image Processing Optimization: Enhanced Pi0.5 model structure for
  improved image processing performance.
- Real-Time Chunking Demo: Demonstrate Pi0.5 with Real-Time
  Chunking (RTC) for accelerated inference on Intel Platforms.

**Known Issues**

- `CL_OUT_OF_RESOURCES` throws an exception when running the Pi0.5
  model inference with the i915 driver on an Intel Ultra 2 Platform.

  > *Workaround: Rebind to XE driver to resolve the issue.*

<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025.md>

:::
hide_directive-->