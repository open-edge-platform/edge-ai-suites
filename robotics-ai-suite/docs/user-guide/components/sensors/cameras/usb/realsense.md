# RealSense USB Depth Cameras

RealSense USB depth cameras provide color, depth, and motion data for robot perception workloads.
Review the [System Requirements](../../../../platform_foundation/system_requirements.md)
before installing camera software.

## Software

Install the RealSense SDK 2.0 packages using the official
[librealsense Linux installation instructions](https://github.com/realsenseai/librealsense/blob/master/doc/distribution_linux.md)

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

For ROS 2 Jazzy, install the required RealSense tools and ROS 2 wrapper from your configured package repositories.

> **NOTE:** Prerequisites for the RealSense packages can be found in the [Getting Started](../../../../platform_foundation/getting_started.md) guide.

```bash
sudo apt update
sudo apt install ros-jazzy-librealsense2-tools ros-jazzy-realsense2-camera
```

:::
:::{tab-item} **Humble**
:sync: humble

For ROS 2 Humble, install the required RealSense tools and ROS 2 wrapper from your configured package repositories.

> **NOTE:** Prerequisites for the RealSense packages can be found in the [Getting Started](../../../../platform_foundation/getting_started.md) guide.

```bash
sudo apt update
sudo apt install ros-humble-librealsense2-tools ros-humble-realsense2-camera
```

:::
::::

## Next steps

- For USB-connected depth cameras, see the
  [RealSense with ROS 2 sample application](../../reference_applications/realsense-ros2.md).

Individual Blueprints can require additional firmware, launch parameters, or
camera calibration. Follow their prerequisites before using a camera in a robot
application.