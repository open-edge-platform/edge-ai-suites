---
title: OpenVINO™ Tutorial with Segmentation
---

This tutorial serves as an example for understanding the utilization of
the ROS 2 OpenVINO™ node. It outlines the steps for installing and
executing the semantic segmentation model using the ROS 2 OpenVINO™
toolkit. This tutorial uses the Intel® RealSense™ camera image as input
and performs inference on CPU, GPU devices.

# Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/apt-setup.html)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-openvino.html)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install.html)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-npu-driver.html)

# Install OpenVINO™ tutorial packages

``` bash
sudo apt install ros-humble-segmentation-realsense-tutorial
```

# Run Demo with Intel® RealSense™ Topic Input

Run one of the following commands to launch the segmentation tutorial
with a specific inference engine:

- GPU inference engine

  ``` 
  ros2 launch segmentation_realsense_tutorial openvino_segmentation.launch.py device:=GPU
  ```

- CPU inference engine

  ``` 
  ros2 launch segmentation_realsense_tutorial openvino_segmentation.launch.py device:=CPU
  ```

> [!NOTE]
> If no device is specified, the GPU is selected by default as inference
> engine.

Once the tutorial is started, the `deeplabv3` model is downloaded,
converted into IR files, and the inference process begins, utilizing the
input from the Intel® RealSense™ camera.

To exit the application, press `Ctrl-c` in the terminal where the launch
script was executed.
