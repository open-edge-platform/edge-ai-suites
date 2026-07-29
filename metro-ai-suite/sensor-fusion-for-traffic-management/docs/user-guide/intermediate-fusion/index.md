# Sensor Fusion for Traffic Management Intermediate-Fusion

<!--hide_directive
<div class="component_card_widget">
   <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/sensor-fusion-for-traffic-management/intermediate-fusion">
     GitHub
  </a>
   <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/sensor-fusion-for-traffic-management/intermediate-fusion/README.md">
     Readme
  </a>
</div>
hide_directive-->

A BEVFusion-based intermediate-fusion reference implementation that deploys camera and lidar
sensor fusion on Intel GPU. The implementation provides two inference pipelines that process
synchronized image and point-cloud streams and output 3D object detections in a KITTI-style
format.

This implementation features two pipelines tailored to different model architectures:

- `bevfusion`: split-model PointPillars pipeline using four ONNX models.
- `bevfusion_unified`: unified SECOND pipeline that runs a single ONNX model with custom
  OpenVINO sparse operations.

Both pipelines target the Intel GPU runtime under OpenVINO and support FP32 and INT8
precision modes.

## Key Features

Discover the key features that set our implementation apart and see how it meets the
intermediate-fusion requirements of your intelligent traffic management solution. For a highly
performant and cost-efficient solution, leverage the Intel-powered
[Certified AI Systems](https://www.intel.com/content/www/us/en/developer/topic-technology/edge-5g/edge-solutions/hardware.html?f:guidetm392b07c604bd49caa5c78874bcb8e3af=%5BIntel%C2%AE%20Edge%20AI%20Box%5D).
Whether you are evaluating a BEVFusion-based detection pipeline or validating your hardware
platform's capabilities, this reference implementation serves as the perfect foundation.

- Intel GPU-accelerated inference using OpenVINO, with iGPU and dGPU support for
  heterogeneous computing configurations.
- Docker-first workflow for rapid validation: pull the published image and run the automated
  smoke test in minutes without a native build.
- Native host build path for production integration, with granular control over precision,
  dataset, and device selection.
- INT8 post-training quantization (PTQ) via NNCF, with per-subgraph precision flags for
  camera backbone, LiDAR PFE, fuser, and detection head.
- KITTI-format evaluation tooling and dataset conversion utilities for DAIR-V2X-I and
  KITTI-360.
- Support for converting NVIDIA CUDA-V2XFusion checkpoints to OpenVINO IR, enabling reuse
  of existing trained models on Intel hardware without retraining.

## Benefits

- **Enhanced AI Performance**: Achieve superior 3D object detection accuracy with
  intermediate-fusion that tightly couples camera and lidar features before the detection
  head, outperforming late-fusion approaches under challenging conditions.
- **Accelerated Time to Market**: Speed up validation by using the pre-built Docker image and
  automated smoke-test scripts, reducing environment setup to a single pull-and-run step.
- **Cost Efficiency**: Lower your inference costs with INT8 quantization on Intel GPU,
  maintaining detection quality while significantly reducing compute and power requirements.
- **Simplified Development**: Reduce integration complexity with a unified build system,
  preset dataset configurations, and reference conversion guides for existing NVIDIA
  checkpoints.

<!--hide_directive
:::{toctree}
:hidden:

Get Started <GSG.md>
Prerequisites <Prerequisites.md>
Testing <Testing.md>
Training <training/training.md>
:::
hide_directive-->
