# OpenVINO™ Tutorial with Segmentation

This tutorial serves as an example for understanding the utilization of the ROS 2 OpenVINO™ node.
It outlines the steps for installing and executing the semantic segmentation model using the ROS 2 OpenVINO™ toolkit.
This tutorial uses the RealSense camera image as input and performs inference on CPU, GPU devices.

## Prerequisites

Complete the [Getting Started](../../../platform_foundation/getting_started.md) guide before continuing.

## Install OpenVINO™ tutorial packages

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
sudo apt install ros-jazzy-segmentation-realsense-tutorial
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
sudo apt install ros-humble-segmentation-realsense-tutorial
```

:::
::::

## Run Demo with RealSense Camera Topic Input

Run one of the following commands to launch the segmentation tutorial with a specific inference engine:

- GPU inference engine

  ```bash
  ros2 launch segmentation_realsense_tutorial openvino_segmentation.launch.py device:=GPU
  ```

- CPU inference engine

  ```bash
  ros2 launch segmentation_realsense_tutorial openvino_segmentation.launch.py device:=CPU
  ```

> **Note:** If no device is specified, the GPU is selected by default as inference engine.

Once the tutorial is started, the ``deeplabv3`` model is downloaded, converted into IR files,
and the inference process begins, utilizing the input from the RealSense camera.

To exit the application, press ``Ctrl-c`` in the terminal where the launch script was executed.

### Troubleshooting

For general robot issues, refer to
the [troubleshooting guide](../../../resources/troubleshooting).
