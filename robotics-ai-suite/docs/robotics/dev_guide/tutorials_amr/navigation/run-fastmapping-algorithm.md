# FastMapping Algorithm

FastMapping application is the Intel® optimized version of octomap.

For more information on FastMapping, see [how_it_works](../../how_it_works/index.rst).

## Source Code

The source code of this component can be found here: [FastMapping](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/fast-mapping)

## Prerequisites

Complete the [get started guide](../../../gsg_robot/index.rst) before continuing.

## Run the FastMapping Standalone Application

1. Install dependencies:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-rtabmap-ros
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get install ros-humble-rtabmap-ros
   ```

   <!--hide_directive:::
   ::::hide_directive-->

2. To download and install the FastMapping standalone sample application run
   the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-fast-mapping
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get install ros-humble-fast-mapping
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note**:
   >
   > The `ros-jazzy-fast-mapping` package includes a ROS 2 bag, which will be used for this tutorial.
   > After the installation, the ROS 2 bag can be found at `/opt/ros/jazzy/share/bagfiles/spinning/`.
   > `ros-humble-fast-mapping` can be found at similar directory path.

3. Set up your ROS 2 environment

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   source /opt/ros/jazzy/setup.bash
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   source /opt/ros/humble/setup.bash
   ```

   <!--hide_directive:::
   ::::hide_directive-->

4. Run the FastMapping sample application using a ROS 2 bag of a robot spinning:

   ```bash
   ros2 launch fast_mapping fast_mapping.launch.py
   ```

   Expected output:

   <https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/docs/robotics/videos/fast_mapping.mp4>

5. Run the FastMapping sample application using Intel® RealSense™ camera
   input with RTAB-Map:

   ```bash
   ros2 launch fast_mapping fast_mapping_rtabmap.launch.py
   ```

Once the tutorial is launched, the input from the Intel® RealSense™ camera is
used and a 3D voxel map of the environment can be viewed in rviz.

To close this application, type `Ctrl-c` in the terminal where you ran
the launch script.

## Troubleshooting

For general robot issues, refer to
[Troubleshooting](../robot-tutorials-troubleshooting.md).
