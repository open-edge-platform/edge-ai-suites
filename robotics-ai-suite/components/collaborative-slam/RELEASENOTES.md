Collaborative SLAM Release Notes
====================

# 2023.1 - Version 0.5

* Added support for region-wise remapping feature that updated
  pre-constructed keyframe/landmark map and octree map with manual
  region input from user in remapping mode.

* Added support for tracker frame-level pose fusion using Kalman
  Filter (part of multi-camera feature).

* Added support for depth image input with float data type.

* Refined the strategy to use odometry data when visual tracking gets
  lost in localization mode.

* Improved the acceleration performance by offloading ORB feature
  extraction for stereo input to GPU. Now for monocular, stereo and
  RGBD input, the tracker node can have almost 50% CPU usage cut down on
  TGL platform if enabling GPU offloading feature.

* Fixed the coordinate alignment issue during the map merging of 2
  octree maps in the fast mapping module.

* Fixed the tracking lost issue in case of robot doing self-rotation.

# Known Limitations

* In case of the long runs, where the server nodes accumulates more than
  80000 keyframes, shutdown process will take more time to exit cleanly.

* For visual-odom fusion with monocular input, once the visual tracking
  is lost, the system will only rely on odometry input (if enabled) to
  sustain tracking and will never be able to switch back to visual
  tracking again.

* The visual-inertial fusion is not supported in localization mode

* For fusion of visual, inertial and odom data at the same time, the
  system is still under development.

* Map merge will not happen if robots are moving in opposite directions
  through common area.

* Local BA and global BA are not considered in the 2D Lidar support.


# Collab SLAM Release Testing

* The collab SLAM is automatically tested on each release with the
  following tests:
  - CPU build test/CPU-GPU build test
  - ROS topic input tests
  - Test for pose movement based on ROS bag file using ROS2 official
    image-transport package
  - Test for IMU system on IMU preintegration and initialization
    based on ROS bag file
  - Test for 2D LiDAR support on LiDAR feature matching and
    frame-to-frame tracking using ROS bag file
  - Map merging test based on ROS bag files
  - Region-wise remapping test based on pre-constructed maps and ROS
    bag file
  - Benchmarks on TUM RGBD/Monocular, KITTI Monocular/Stereo, EuRoC
    Monocular/Stereo and EuRoC Monocular/Stereo with IMU input
  - Static code, virus and various security analysis scans


# Test Hardware / Software

## Setup:

### Hardware


* [Pengo](https://wiki.cogni.io/Category:Pengo)/[Segway](https://www.segway.com/robotics/commercial/)/[AAEON](https://up-shop.org/ehl-tgl-robotic.html#additional)/[TurtleBot](https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/)

* Realsense D435/D435i/D455

* TGL

### Software

* Ubuntu 20.04

* ROS Foxy

# Previous versions

# 2022 Q4 - Version 0.4

* Added support to save octree map in mapping mode, then load and
  visualize it in localization mode.

* Added support of 2D Lidar based frame-to-frame tracking for RGBD input.

* Added on-demand synchronization option to keep octree map consistent
  among multiple trackers.

* Added support for stereo fisheye input (i.e. RealSense T265).

* Highly reduced the tracker <-> server communication message delay in
  localization mode, especially for the case of multiple trackers.

* Removed the outdated ROS1 related code, re-organize the config
  files and launch files, refined documentation.

# 2022 Q3 - Version 0.3

* Added support for Orb Extractor with C for Metal using OneAPI Level
  Zero interface.

* Added support for stereo input in EuRoC dataset

* Added support for both monocular and stereo input in KITTI dataset

* Fixed the issue with memory consumption in localization mode when
  re-localizing.

* Added relocalization mode

* Fast Mapping integration: basic, loop closure and map merge

* Highly reduced tracker <-> server communication bandwidth in both
  mapping and localization mode

* Unified benchmark scripts and added new functionalities


# 2022 Q2 - Version 0.2

* Support for visual-inertial based tracking with enhanced performance.
  If robot or a camera contains IMU, it can be leveraged to improve tracking.
  Monocular and RGBD inputs are supported. For monocular input, IMU can be
  used to obtain the absolute scale.

* Improved localization mode using odometry data.

* Fixed the issue dropping frames due to QoS ROS2 subscribe policy.
  Before tracker could drop up to 20% frames.

* Fixed the issue where rviz does not show full trajectory.


# 2022 Q1 - Version 0.1

* Initial implementation of Collaborative SLAM which partitions tracker
  and server as SLAM frontend and backend in order to offload map
  management and optimization to edge server.

* Multiple robots running tracker collaboratively to build and merge maps
  in the same environment with real-time communication with server and
  less bandwidth usage.

* Efficient coordinate-based landmark management and retrieval with
  the grid map to improve localization robustness.

* Hierarchical segment-based optimization for SLAM to speedup global
  optimization for large maps.

* Supports localization and mapping modes.

* Joint fusion and optimization of visual inertial and odometry data.

