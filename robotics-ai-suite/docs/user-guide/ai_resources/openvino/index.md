# OpenVINO

[OpenVINO](https://docs.openvino.ai/) is the primary toolkit for optimizing and
deploying deep-learning inference in Robotics AI Suite applications. It supports
models from common frameworks and can target available Intel compute devices.

Use the current [OpenVINO installation documentation](https://docs.openvino.ai/latest/get-started/install-openvino.html) for the selected environment.

## Reference Applications

OpenVINO reference applications cover object detection, segmentation, and
RealSense camera workflows.


::::{grid} 2

:::{grid-item-card} **Semantic Segmentation with RealSense**
:link: reference_applications/segmentation_realsense_tutorial
:link-type: doc
:link-alt: clickable cards

Run semantic segmentation on RealSense image data using OpenVINO inference.
:::

:::{grid-item-card} **Object Detection**
:link: reference_applications/object_detection_tutorial
:link-type: doc
:link-alt: clickable cards

Deploy object-detection workloads with ROS 2 camera inputs and OpenVINO acceleration.
:::

:::{grid-item-card} **OpenVINO Multi-Camera Demo**
:link: reference_applications/openvino_multicam_demo
:link-type: doc
:link-alt: clickable cards

Process multiple camera streams in a single OpenVINO-powered demo pipeline.
:::

:::{grid-item-card} **YOLOv8 with OpenVINO**
:link: reference_applications/yolov8_openvino_tutorial
:link-type: doc
:link-alt: clickable cards

Use a YOLOv8 model with OpenVINO for accelerated object detection on robotics systems.
:::

:::{grid-item-card} **OpenVINO Model Guidance**
:link: models/index
:link-type: doc
:link-alt: clickable cards

Optimize and deploy perception, manipulation, and vision-language-action models with OpenVINO.
:::

:::{grid-item-card} **Pi0.5 Model Optimization**
:link: pi05-optimization
:link-type: doc
:link-alt: clickable cards

Convert, compress, benchmark, and validate the Pi0.5 vision-language-action model.
:::
::::



:::{toctree}
:hidden:

Reference Applications <reference_applications/index>
models/index
pi05-optimization
OpenVINO Physical AI Runtime <https://github.com/openvinotoolkit/physicalai>
:::


## Additional Guidance

- [OpenVINO model guidance](models/index.md) includes reusable perception,
  manipulation, and foundation-model guidance. The workflows require the
    [platform getting-started guide](../../platform_foundation/getting_started.md)
    when used with the Humanoid Toolkit.

## Benchmarking

Use the upstream [OpenVINO Benchmark Tool](https://docs.openvino.ai/2026/get-started/learn-openvino/openvino-samples/benchmark-tool.html)
to estimate deep-learning inference throughput and latency on supported Intel®
devices. Install OpenVINO and its samples with the [OpenVINO sample guidance](https://docs.openvino.ai/2026/get-started/learn-openvino/openvino-samples/get-started-demos.html)
before benchmarking.

Use the same OpenVINO version to convert a model and to run inference unless the
model's documentation explicitly supports a different compatibility path.
