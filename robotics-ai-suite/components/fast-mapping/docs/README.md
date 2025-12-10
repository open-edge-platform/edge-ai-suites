<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# FastMapping Algorithm

---

FastMapping application is the Intel® optimized version of octomap.

## Source Code

The source code of this component can be found here:
[FastMapping](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/fast-mapping)

## Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/apt-setup.html)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/install-openvino.html)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/install.html)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/install-npu-driver.html)

## Run the FastMapping Standalone Application
1. If Ubuntu 22.04 with Humble is used, then run

```bash
source /opt/ros/humble/setup.bash
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
source /opt/ros/jazzy/setup.bash
```

This command will set `ROS_DISTRO` env var that is used in following steps.

2. To download and install the FastMapping standalone sample
    application run the command below:

    ``` bash
    sudo apt-get install ros-${ROS_DISTRO}-fast-mapping
    ```

    > [!NOTE]
    > The `ros-${ROS_DISTRO}-fast-mapping` package includes a ROS 2 bag, which
    > will be used for this tutorial. After the installation, the ROS 2
    > bag can be found at `/opt/ros/${ROS_DISTRO}$/share/bagfiles/spinning/`

3. Run the FastMapping sample application using a ROS 2 bag of a robot
    spinning:

    ``` bash
    ros2 launch fast_mapping fast_mapping.launch.py
    ```

4. Run the FastMapping sample application using Intel® RealSense™
    camera input with RTAB-Map:

    ```bash
    sudo apt install ros-${ROS_DISTRO}-rtabmap-ros
    ros2 launch fast_mapping fast_mapping_rtabmap.launch.py
    ```

Once the tutorial is launched, the input from the Intel® RealSense™
camera is used and a 3D voxel map of the environment can be viewed in
rviz.

To close this application, type `Ctrl-c` in the terminal where you ran
the launch script.
