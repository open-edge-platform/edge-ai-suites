# FastMapping Algorithm

FastMapping application is the Intel® optimized version of octomap.

## Source Code

The source code of this component can be found here: [FastMapping](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/fast-mapping)

## Prerequisites

Complete the [Getting Started](../../platform_foundation/getting_started.md) guide before continuing.

## Run the FastMapping Standalone Application

1. Install dependencies:

   ::::{tab-set}
   :::{tab-item} **Jazzy**
   :sync: jazzy

   ```bash
   sudo apt-get install ros-jazzy-rtabmap-ros
   ```

   :::
   :::{tab-item}  **Humble**
   :sync: humble

   ```bash
   sudo apt-get install ros-humble-rtabmap-ros
   ```

   :::
   ::::

2. To download and install the FastMapping standalone sample application run
   the command below:

   ::::{tab-set}
   :::{tab-item} **Jazzy**
   :sync: jazzy

   ```bash
   sudo apt-get install ros-jazzy-fast-mapping
   ```

   :::
   :::{tab-item}  **Humble**
   :sync: humble

   ```bash
   sudo apt-get install ros-humble-fast-mapping
   ```

   :::
   ::::

   > **Note**:
   >
   > The `ros-jazzy-fast-mapping` package includes a ROS 2 bag, which will be used for this tutorial.
   > After the installation, the ROS 2 bag can be found at `/opt/ros/jazzy/share/bagfiles/spinning/`.
   > `ros-humble-fast-mapping` can be found at similar directory path.

3. Set up your ROS 2 environment

   ::::{tab-set}
   :::{tab-item} **Jazzy**
   :sync: jazzy

   ```bash
   source /opt/ros/jazzy/setup.bash
   ```

   :::
   :::{tab-item}  **Humble**
   :sync: humble

   ```bash
   source /opt/ros/humble/setup.bash
   ```

   :::
   ::::

4. Run the FastMapping sample application using a ROS 2 bag of a robot spinning:

   ```bash
   ros2 launch fast_mapping fast_mapping.launch.py
   ```

   Expected output:

   <https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/docs/user-guide/software_references/amr/videos/fast_mapping.mp4>

5. Run the FastMapping sample application using RealSense camera
   input with RTAB-Map:

   ```bash
   ros2 launch fast_mapping fast_mapping_rtabmap.launch.py
   ```

Once the tutorial is launched, the input from the RealSense camera is
used and a 3D voxel map of the environment can be viewed in rviz.

To close this application, type `Ctrl-c` in the terminal where you ran
the launch script.

## Troubleshooting

For general robot issues, refer to
the [troubleshooting guide](../../resources/troubleshooting).
