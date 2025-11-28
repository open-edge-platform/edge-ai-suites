# Collaborative Visual SLAM

Collaborative Visual SLAM is compiled natively for both Intel® Core™ and Intel Atom® processor-based systems.
In addition, GPU acceleration may be enabled on selected Intel® Core™ processor-based system.
The default installation of Collaborative Visual SLAM is designed to run on the widest range of processors.

## Source Code

The source code of this component can be found here:
[Collaborative-Slam](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/collaborative-slam)

## Prerequisites

Complete the [get started guide](../../../gsg_robot/index.rst) before continuing.

## Collaborative Visual SLAM Versions Available

- Intel SSE-only CPU instruction accelerated package for Collaborative SLAM (installed by default):

  ```bash
  # Required for Intel® Atom® processor-based systems
  sudo apt-get install ros-humble-collab-slam-sse
  ```

- Intel AVX2 CPU instruction accelerated package for Collaborative SLAM:

   ```bash
   # Works only on Intel® Core™ processor-based systems
   sudo apt-get install ros-humble-collab-slam-avx2
   ```

- Intel GPU Level-Zero accelerated package for Collaborative SLAM:

   ```bash
   # Works only on 9th, 11th or 12th Generation Intel® Core™ processors with Intel® Iris® Xe Integrated Graphics or Intel® UHD Graphics
   sudo apt-get install ros-humble-collab-slam-lze
   ```

The tutorials below should work for any compatible version of Collaborative Visual SLAM that is installed.
Use the instructions above to switch between version to experiment with different accelerations.

> **Note**:
> When installing a collaborative SLAM package, use the specified command line tool
> below to identify the integrated GPU on your system. Once determined, select
> the GPU during the installation process. Select option `3. gen12lp`, if unsure.
>
> ```console
> Configuring liborb-lze
> ----------------------
> Select the Intel integrated GPU present on this system. Hint: In another
> terminal install 'intel-gpu-tools' (sudo apt install intel-gpu-tools), then
> execute 'intel_gpu_top' to view CPU/GPU details (sudo intel_gpu_top -L)
>
> 1. gen9  2. gen11  3. gen12lp
> Select GPU Generation (1, 2, or 3):
> ```

## Select a Collaborative Visual SLAM Tutorial to Run

- [Collaborative Visual SLAM with Two Robots](#collaborative-visual-slam-with-two-robots):
  uses as input two ROS 2 bags that simulate two
  robots exploring the same area

  - The ROS 2 tool rviz2 is used to visualize the two robots, the server, and
    how the server merges the two local maps of the robots into one common
    map.
  - The output includes the estimated pose of the camera and visualization of
    the internal map.
  - All input and output are in standard ROS 2 formats.

- [Collaborative Visual SLAM with FastMapping Enabled](#collaborative-visual-slam-with-fastmapping-enabled):
  uses as an input a ROS 2 bag that simulates a robot
  exploring an area

  - Collaborative visual SLAM has the FastMapping algorithm integrated.
  - For more information on FastMapping, see [how_it_works](../../how_it_works/index.rst).
  - The ROS 2 tool rviz2 is used to visualize the robot exploring the area and
    how FastMapping creates the 2D and 3D maps.

- [Collaborative Visual SLAM with Multi-Camera Feature](#collaborative-visual-slam-with-multi-camera-feature):
  uses as an input a ROS 2 bag that simulates a robot with two
  Intel® RealSense™ cameras exploring an area.

  - Collaborative visual SLAM enables tracker frame-level pose fusion using Kalman
    Filter (part of loosely coupled solution for multi-camera feature).
  - The ROS 2 tool rviz2 is used to visualize estimated pose of different cameras.

- [Collaborative Visual SLAM with 2D Lidar Enabled](#collaborative-visual-slam-with-2d-lidar-enabled):
  uses as an input a ROS 2 bag that simulates a robot exploring an area

  - Collaborative visual SLAM enables 2D Lidar based frame-to-frame tracking for RGBD input.
  - The ROS 2 tool rviz2 is used to visualize the trajectory of robot when 2D Lidar is used.

- [Collaborative Visual SLAM with Region-wise Remapping Feature](#collaborative-visual-slam-with-region-wise-remapping-feature):
  uses as an input a ROS 2 bag that simulates a robot to update pre-constructed
  keyframe/landmark map and 3D octree map with manual region input from user in remapping mode.

  - The ROS 2 tool rviz2 is used to visualize the process of region-wise remapping feature
    including loading and updating the pre-constructed keyframe/landmark and 3D octree map.

### Collaborative Visual SLAM with Two Robots

1. To download and install the tutorial run the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-cslam-tutorial-two-robot
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   sudo apt-get install ros-humble-cslam-tutorial-two-robot
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note:** In this installation package, there are two substantial ROS 2
   > bag files, which are approximately 6.8 GB and 2.6 GB in size.

2. Run the Collaborative Visual SLAM algorithm using two bags simulating two
   robots going through the same area:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   /opt/ros/jazzy/share/collab-slam/tutorial-two-robot/cslam-two-robot.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   /opt/ros/humble/share/collab-slam/tutorial-two-robot/cslam-two-robot.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   Expected result: On the server rviz2, both trackers are seen.

   - Red indicates the path robot 1 is taking right now.
   - Blue indicates the path robot 2 took.
   - Green indicates the points known to the server.

    ![collab_slam](../../../images/collab_slam.gif)

3. You may stop execution of the script any time by pressing CTRL-C.

   This tutorial demo is complete when the output to the console indicates that
   no further images are being processed.
   (hint: look for the output, "got 0 images in past 3.0s"). Press CTRL-C when
   you see this to stop the executing script.

   ```console
   [univloc_tracker_ros-1] [INFO] [1694539167.880197983] [univloc_tracker_0]: UnivLoc (unconnected) got 0 images in past 3.0s. Localized/processed 0/0 (0.00 Hz). Totally 2525/2525 (100.00%).
   ```

### Collaborative Visual SLAM with FastMapping Enabled

1. To download and install the tutorial run the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-cslam-tutorial-fastmapping
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   sudo apt-get install ros-humble-cslam-tutorial-fastmapping
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note**: In this installation package, there is a substantial ROS 2
   > bag file, which is approximately 6.8 GB in size.

2. Run the collaborative visual SLAM algorithm with FastMapping enabled:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   /opt/ros/jazzy/share/collab-slam/tutorial-fastmapping/cslam-fastmapping.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   /opt/ros/humble/share/collab-slam/tutorial-fastmapping/cslam-fastmapping.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   Expected result: On the opened rviz2, you see the visual SLAM keypoints, the
   3D map, and the 2D map.

3. You can disable the `/univloc_tracker_0/local_map`,
   `univloc_tracker_0/fused_map`, or both topics.

   **Visible Test: Showing keypoints, the 3D map, and the 2D map**

   *Expected Result:*

   ![c-slam-fm-full](../../../images/c-slam-fm-full.png)

   **Visible Test: Showing the 3D map**

   *Expected Result:*

   ![c-slam-fm-3D](../../../images/c-slam-fm-3D.png)

   **Visible Test: Map showing the 2D map**

   *Expected Result:*

   ![c-slam-fm-2D](../../../images/c-slam-fm-2D.png)

   **Visible Test: Showing keypoints and the 2D map**

   *Expected Result:*

   ![c-slam-fm-keypoints](../../../images/c-slam-fm-keypoints.png)

4. You may stop execution of the script any time by pressing CTRL-C.
   This tutorial demo is complete when the output to the console indicates that
   no further images are being processed.
   (hint: look for the output, "got 0 images in past 3.0s"). Press CTRL-C when
   you see this to stop the executing script.

   ```console
   [univloc_tracker_ros-1] [INFO] [1694539167.880197983] [univloc_tracker_0]: UnivLoc (unconnected) got 0 images in past 3.0s. Localized/processed 0/0 (0.00 Hz). Totally 2525/2525 (100.00%).
   ```

### Collaborative Visual SLAM with Multi-Camera Feature

> **Note**: The following part illustrates part of the multi-camera feature in Collaborative SLAM that
> uses Kalman Filter to fuse SLAM poses from different trackers in a loosely-coupled manner,
> and we treat each individual camera as a separate tracker (ROS 2 node). For other parts of the multi-camera feature,
> they are not yet ready and will be integrated later.

1. To download and install the tutorial run the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-cslam-tutorial-multi-camera
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   sudo apt-get install ros-humble-cslam-tutorial-multi-camera
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note**: In this installation package, there is a substantial ROS 2
   > bag file, which is approximately 206 MB in size.

2. Run the collaborative visual SLAM algorithm tracker frame-level pose fusion
   using Kalman Filter:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   /opt/ros/jazzy/share/collab-slam/tutorial-multi-camera/cslam-multi-camera.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   /opt/ros/humble/share/collab-slam/tutorial-multi-camera/cslam-multi-camera.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   **Expected result:** On the opened rviz windows, you see the pose trajectory
   outputs for each camera.

3. You may stop execution of the script any time by pressing CTRL-C.
   This tutorial demo is complete when the output to the console indicates that
   no further images are being processed.
   (hint: look for the output, "got 0 images in past 3.0s"). Press CTRL-C when
   you see this to stop the executing script.

   ```console
   [univloc_tracker_ros-1] [INFO] [1694539167.880197983] [univloc_tracker_0]: UnivLoc (unconnected) got 0 images in past 3.0s. Localized/processed 0/0 (0.00 Hz). Totally 2525/2525 (100.00%).
   ```

4. Afterwards, run the Python script to visualize the three trajectories
   obtained from ROS 2 topics: `univloc_tracker_0/kf_pose`, `univloc_tracker_2/kf_pose`, `/odometry/filtered`.

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   cd /tmp/
   python3 /opt/ros/jazzy/share/collab-slam/tutorial-multi-camera/traj-compare.py
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   cd /tmp/
   python3 /opt/ros/humble/share/collab-slam/tutorial-multi-camera/traj-compare.py
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   Expected result: On the Python window, three trajectories are shown.
   An example image is as follows:

   - Blue indicates the trajectory generated by front camera.
   - Gray indicates the trajectory generated by rear camera.
   - Red indicates the fused trajectory generated by Kalman Filter.

   The trajectory from Kalman Filter should be the fused result of the other two trajectories
   indicating the multi-camera pose fusion is working properly.

   ![compare_trajectories](../../../images/compare_trajectories.png)

5. You may stop execution of the Python script any time by closing the chart window.

### Collaborative Visual SLAM with 2D Lidar Enabled

1. To download and install the tutorial run the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-cslam-tutorial-2d-lidar
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   sudo apt-get install ros-humble-cslam-tutorial-2d-lidar
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note**: In this tutorial installation, there is a substantial ROS 2
   > bag file, which is approximately 3.7 GB in size.

2. Run the collaborative visual SLAM algorithm with auxiliary Lidar data input:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   /opt/ros/jazzy/share/collab-slam/tutorial-2d-lidar/cslam-2d-lidar.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   /opt/ros/humble/share/collab-slam/tutorial-2d-lidar/cslam-2d-lidar.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

3. Use a separate terminal to debug and capture the output ROS 2 topic.
   You can check if certain topic has been published and view its messages.

   ```bash
   ros2 node list
   ros2 topic list
   ros2 topic echo /univloc_tracker_0/lidar_states
   ```

   Expected result: the values of `pose_failure_count` and `feature_failure_count` should not be 0,
   since they are the default values and should increase over time. On the opened rviz,
   you see the pose trajectory when Lidar data is used.

   ```console
   header:
   stamp:
      sec: 1
      nanosec: 683876706
   frame_id: ''
   feature_failure_count: 30
   pose_failure_count: 1
   ```

   ![use_lidar](../../../images/use_lidar.png)

4. You may stop execution of the script any time by pressing CTRL-C.

   This tutorial demo is complete when the output to the console indicates that
   no further images are being processed.
   (hint: look for the output, "got 0 images in past 3.0s"). Press CTRL-C when
   you see this to stop the executing script.

   ```console
   [univloc_tracker_ros-1] [INFO] [1694539167.880197983] [univloc_tracker_0]: UnivLoc (unconnected) got 0 images in past 3.0s. Localized/processed 0/0 (0.00 Hz). Totally 2525/2525 (100.00%).
   ```

### Collaborative Visual SLAM with Region-wise Remapping Feature

1. To download and install the tutorial run the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-cslam-tutorial-region-remap
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   sudo apt-get install ros-humble-cslam-tutorial-region-remap
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note**: In this tutorial installation, there is a substantial ROS 2
   > bag file, which is approximately 2.6 GB in size.

2. Run the collaborative visual SLAM algorithm tracker frame-level pose fusion
   using Kalman Filter:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   /opt/ros/jazzy/share/collab-slam/tutorial-region-remap/cslam-region-map.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   /opt/ros/humble/share/collab-slam/tutorial-region-remap/cslam-region-map.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   Expected result: On the opened server rviz, you see the keyframe and landmark
   constructed in mapping mode.

   ![constructed_keyframes](../../../images/constructed_keyframes_and_landmarks_map.png)

   On the opened tracker rviz, you see the 3D octree map constructed in mapping mode.

   ![constructed_octree_map](../../../images/constructed_octree_map.png)

3. You may stop execution of the script any time by pressing CTRL-C.

   This tutorial demo is complete when the output to the console indicates that
   no further images are being processed.
   (hint: look for the output, "got 0 images in past 3.0s"). Press CTRL-C when
   you see this to stop the executing script.

   ```console
   [univloc_tracker_ros-1] [INFO] [1694539167.880197983] [univloc_tracker_0]: UnivLoc (unconnected) got 0 images in past 3.0s. Localized/processed 0/0 (0.00 Hz). Totally 2525/2525 (100.00%).
   ```

4. Run the collaborative visual SLAM algorithm in remapping mode to load and
   update pre-constructed keyframe/landmark and 3D octree map:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   /opt/ros/jazzy/share/collab-slam/tutorial-region-remap/cslam-region-remap.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   /opt/ros/humble/share/collab-slam/tutorial-region-remap/cslam-region-remap.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   **Expected result**: On the opened server rviz, you see the loaded pre-constructed keyframe/landmark map
   in mapping mode. Within the remapping region, corresponding map will be deleted.

   ![loaded_keyframes]( ../../../images/loaded_keyframes_and_landmarks_map.png)

   On the opened tracker rviz, initially you see the loaded 3D octree map.

   ![loaded_octree_map](../../../images/loaded_octree_map.png)

   On the opened tracker rviz, after bag playing is done, you see the 3D octree map inside the remapping region will be updated.

   ![updated_map](../../../images/updated_map_after_remapping.png)

5. You may stop execution of the script any time by pressing CTRL-C.

   This tutorial demo is complete when the output to the console indicates that
   no further images are being processed.
   (hint: look for the output, "got 0 images in past 3.0s"). Press CTRL-C when
   you see this to stop the executing script.

   ```console
   [univloc_tracker_ros-1] [INFO] [1694539167.880197983] [univloc_tracker_0]: UnivLoc (unconnected) got 0 images in past 3.0s. Localized/processed 0/0 (0.00 Hz). Totally 2525/2525 (100.00%).
   ```

## Collaborative Visual SLAM with GPU Offloading

With Intel GPU Level-Zero accelerated package for Collaborative SLAM installed,
it is possible to check GPU usage while a tutorial is actively executing.

- In a terminal, check how much of the GPU is using
  `intel-gpu-top`.

  ```bash
  # Ensure the package is installed
  sudo apt-get install intel-gpu-tools

  # The follow tool will then be available to execute
  sudo intel_gpu_top
  ```

  ![kudan_slam_gpu_top](../../../images/kudan_slam_gpu_top.png)

## Troubleshooting

- IMU functionality does not currently work properly for the AVX2 and GPU
  Level-Zero accelerated packages. Please use the SSE-only version of
  Collaborative SLAM for IMU.

- The odometry feature `use_odom:=true` does not work with these bags.

  The ROS 2 bags used in this example do not have the necessary topics recorded
  for the odometry feature of collaborative visual SLAM.

  If the `use_odom:=true` parameter is set, the `collab-slam` reports
  errors.

- For general robot issues, refer to
  [Troubleshooting](../robot-tutorials-troubleshooting.rst).
