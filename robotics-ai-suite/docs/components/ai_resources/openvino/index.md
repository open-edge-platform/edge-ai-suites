# OpenVINO

[OpenVINO](https://docs.openvino.ai/) is the primary toolkit for optimizing and
deploying deep-learning inference in Robotics AI Suite applications. It supports
models from common frameworks and can target available Intel compute devices.

Use the current [OpenVINO installation documentation](https://docs.openvino.ai/latest/get-started/install-openvino.html) for the selected environment.

## Reference Applications

OpenVINO reference applications cover object detection, segmentation, and
RealSense camera workflows.

<!--hide_directive
::::{grid} 2hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Semantic Segmentation with RealSense**
<!--hide_directive:link: reference_applications/segmentation_realsense_tutorial
:link-type: doc
:link-alt: clickable cardshide_directive-->

Run semantic segmentation on RealSense image data using OpenVINO inference.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Object Detection**
<!--hide_directive:link: reference_applications/object_detection_tutorial
:link-type: doc
:link-alt: clickable cardshide_directive-->

Deploy object-detection workloads with ROS 2 camera inputs and OpenVINO acceleration.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **OpenVINO Multi-Camera Demo**
<!--hide_directive:link: reference_applications/openvino_multicam_demo
:link-type: doc
:link-alt: clickable cardshide_directive-->

Process multiple camera streams in a single OpenVINO-powered demo pipeline.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **YOLOv8 with OpenVINO**
<!--hide_directive:link: reference_applications/yolov8_openvino_tutorial
:link-type: doc
:link-alt: clickable cardshide_directive-->

Use a YOLOv8 model with OpenVINO for accelerated object detection on robotics systems.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **OpenVINO Model Guidance**
<!--hide_directive:link: models/index
:link-type: doc
:link-alt: clickable cardshide_directive-->

Optimize and deploy perception, manipulation, and vision-language-action models with OpenVINO.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Pi0.5 Model Optimization**
<!--hide_directive:link: pi05-optimization
:link-type: doc
:link-alt: clickable cardshide_directive-->

Convert, compress, benchmark, and validate the Pi0.5 vision-language-action model.
<!--hide_directive:::
::::
hide_directive-->

<!--hide_directive
:::{toctree}
:hidden:

Reference Applications <reference_applications/index>
models/index
pi05-optimization
OpenVINO Physical AI Runtime <https://github.com/openvinotoolkit/physicalai>
:::
hide_directive-->

## Additional Guidance

- [OpenVINO model guidance](models/index.md) includes reusable perception,
  manipulation, and foundation-model guidance. The workflows require the
    [platform getting-started guide](../../../platform_foundation/getting_started.md)
    when used with the Humanoid Toolkit.

## Benchmarking

Use the upstream [OpenVINO Benchmark Tool](https://docs.openvino.ai/2026/get-started/learn-openvino/openvino-samples/benchmark-tool.html)
to estimate deep-learning inference throughput and latency on supported Intel®
devices. Install OpenVINO and its samples with the [OpenVINO sample guidance](https://docs.openvino.ai/2026/get-started/learn-openvino/openvino-samples/get-started-demos.html)
before benchmarking.

Use the same OpenVINO version to convert a model and to run inference unless the
model's documentation explicitly supports a different compatibility path.
