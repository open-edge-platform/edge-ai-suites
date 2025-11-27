# OpenVINO™ Object Detection Tutorial

This tutorial is an example for understanding the utilization of the ROS 2 node with OpenVINO™ toolkit.
It outlines the steps for installing the node and executing the object detection model.
Object detection is performed using the OpenVINO™ toolkit. The node is configured to accept dynamically
device parameters (NPU, GPU, or CPU) to specify which inference engine should be used.

## Source Code

The source code of this component can be found here:
[Object-Detection](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/object-detection)

## Prerequisites

Complete the [GSG robot guide](../../../../gsg_robot/index.rst) before continuing.

## Install OpenVINO™ toolkit tutorial packages

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
sudo apt install ros-jazzy-object-detection-tutorial
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
sudo apt install ros-humble-object-detection-tutorial
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

## Run Demo with Image Input

Run one of the following commands to launch the object detection node with a specific inference engine:

- GPU inference engine

  ```bash
  ros2 launch object_detection_tutorial openvino_object_detection.launch.py device:=GPU
  ```

- CPU  inference engine

  ```bash
  ros2 launch object_detection_tutorial openvino_object_detection.launch.py device:=CPU
  ```

- NPU  inference engine

  ```bash
  ros2 launch object_detection_tutorial openvino_object_detection.launch.py device:=NPU
  ```

> **Note:** If no device is specified, the GPU is selected by default as an inference engine.

Once the tutorial is started, the ``mobilenetssd`` model is downloaded, converted into IR files, and the inference process begins.

## Expected Output

![Object_detection](../../../../images/Object_detection.png)

To close this application, type ``Ctrl-c`` in the terminal where you ran the launch script.

### Troubleshooting

For general robot issues, refer to
[Troubleshooting](../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting.rst).
