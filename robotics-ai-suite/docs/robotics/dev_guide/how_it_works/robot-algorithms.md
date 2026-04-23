# Autonomous Mobile Robot Algorithms

Autonomous Mobile Robot includes reference algorithms as well as deep learning models, providing practical examples of automated robot control functions.

## Open Model Zoo for OpenVINO™

The Open Model Zoo for OpenVINO™ toolkit delivers optimized deep learning models and a set of demos to expedite development of high-performance deep learning inference applications. You can use these pre-trained models instead of training your own models to speed up the development and production deployment process.

For details, see [Model Zoo](https://github.com/openvinotoolkit/open_model_zoo).

## ADBSCAN

**Tutorial**: [ADBSCAN Algorithm](../tutorials_amr/navigation/adbscan/index.md)

DBSCAN (Density-Based Spatial Clustering of Applications with Noise) is an unsupervised clustering algorithm that clusters high-dimensional points based on their distribution density. Adaptive DBSCAN (ADBSCAN) has clustering parameters that are adaptive based on range and are especially suitable for processing LiDAR data. It improves the object detection range by 20-30% on average.

## 3D Pointcloud Groundfloor Segmentation

**Tutorial**: [3D Pointcloud Groundfloor Segmentation for Intel® RealSense™ Camera and 3D LiDAR](../tutorials_amr/perception/pointcloud-groundfloor-segmentation.md)

An algorithm, along with a demo application, transforms Intel® RealSense™ Depth Camera images to 3D pointclouds. This algorithm further assigns classification labels such as ground floor or obstacle to each point, delivering both the resulting and filtered pointclouds as output.

## ROS 2 Depth Image to Laser Scan

ROS 2 Depth Image to Laser Scan converts a depth image to a laser scan for use with navigation and localization.

## IMU Tools

IMU Tools, filters and visualizers, from [IMU Tools for ROS](https://github.com/CCNYRoboticsLab/imu_tools):

- **imu_filter_madgwick**: A filter that fuses angular velocities, accelerations, and optionally magnetic readings from a generic IMU device into an orientation.
- **imu_complementary_filter**: A filter that fuses angular velocities, accelerations, and optionally magnetic readings from a generic IMU device into an orientation quaternion using a complementary fusion approach.
- **rviz_imu_plugin**: A plugin for rviz that displays sensor_msgs::Imu messages.

## FastMapping

**Tutorial**: [FastMapping Algorithm](../tutorials_amr/navigation/run-fastmapping-algorithm.md)

FastMapping is an algorithm to create a 3D voxel map of a robot's surroundings based on Intel® RealSense™ Depth Camera sensor data.

## Collaborative Visual SLAM

**Tutorial**: [Collaborative Visual SLAM](../tutorials_amr/navigation/collaborative-slam.md)

Collaborative visual SLAM is a framework for service robots that utilizes simultaneous localization and mapping (SLAM). An edge server maintains a map database and handles global optimization. Each robot can register to an existing map, update it, or build new maps, all through a unified interface with low computation and memory costs. A collaborative visual SLAM system consists of at least two elements:

- The **tracker** is a visual SLAM system with support for inertial and odometry input. It estimates the camera pose in real time and maintains a local map. It can work without a server, but if a server is configured, it communicates with the server to query and update the map. The tracker represents a robot. There can be multiple trackers running at the same time.
- The **server** maintains the maps and communicates with all trackers. For each new keyframe from a tracker, it detects possible loops, both intra-map and inter-map. Once detected, the server performs map optimization or map merging and distributes the updated map to corresponding trackers.

For collaborative visual SLAM details, refer to [A Collaborative Visual SLAM Framework for Service Robots paper](https://arxiv.org/abs/2102.03228).

## ROS 2 Cartographer

ROS 2 Cartographer is a system that provides real-time simultaneous localization and mapping (SLAM) based on real-time 2D LiDAR sensor data. It is used to generate as-built floor plans in the form of occupancy grids.

RTAB-Map (Real-Time Appearance-Based Mapping) is an RGB-D, Stereo, and LiDAR graph-based SLAM approach, employing an incremental appearance-based loop closure detector. This detector uses a bag-of-words approach to determine how likely a new image comes from a previous location or a new location. When a loop closure hypothesis is accepted, a new constraint is added to the map graph, followed by graph optimization to minimize errors. A memory management approach is used to restrict the number of locations used for loop closure detection and graph optimization so that real-time constraints on large-scale environments are consistently met. RTAB-Map can be used alone with a handheld Kinect, a stereo camera, or a 3D LiDAR for 6DoF mapping, or on a robot equipped with a laser rangefinder for 3DoF mapping.

## SLAM Toolbox

The SLAM toolbox is a set of tools and capabilities for 2D SLAM that includes the following:

- Starting, mapping, saving pgm files, and saving maps for 2D SLAM mobile robotics.
- Refining, remapping, or continuing mapping of a saved serialized pose graph at any time.
- Loading a saved pose graph to continue mapping in a space while also removing extraneous information from newly added scans (life-long mapping).
- An optimization-based localization mode built on the pose graph. Optionally run localization mode without a prior map for LiDAR odometry mode with local loop closures.
- Synchronous and asynchronous mapping modes.
- Kinematic map merging with an elastic graph manipulation merging technique in progress.
- Plugin-based optimization solvers with an optimized Google* Ceres-based plugin.
- rviz2 plugin for interacting with the tools.
- Graph manipulation tools in rviz2 to manipulate nodes and connections during mapping.
- Map serialization and lossless data storage.
- See also <https://github.com/SteveMacenski/slam_toolbox>.

## ITS Global Path Planner

**Tutorial**: [ITS Path Planner ROS 2 Navigation Plugin](../tutorials_amr/navigation/its-path-planner-plugin.md)

The Intelligent Sampling and Two-Way Search (ITS) Global Path Planner is a plugin for the ROS 2 Navigation package. It performs a path planning search on a roadmap from two directions simultaneously. The main inputs are a 2D occupancy grid map, robot position, and goal position. The occupancy is converted into a roadmap and can be saved for future inquiries. The output is a list of waypoints that constructs the global path. All inputs and outputs are in standard ROS 2 formats. This plugin is a global path planner module based on Intelligent Sampling and Two-Way Search (ITS).

Currently, the ITS plugin does not support continuous replanning. To use this plugin, a simple behavior tree with compute path to pose and follow path should be used. The inputs for the ITS planner are global 2d_costmap (nav2_costmap_2d::Costmap2D), start pose, and goal pose (geometry_msgs::msg::PoseStamped). The outputs are 2D waypoints of the path. The ITS planner gets the 2d_costmap and converts it to either a Probabilistic Road Map (PRM) or Deterministic Road Map (DRM). The generated roadmap is saved in a txt file that can be reused for multiple inquiries. Once a roadmap is generated, ITS conducts a two-way search to find a path from source to destination. Either the smoothing filter or Catmull spline interpolation can be used to create a smooth and continuous path. The generated smooth path is in the form of ROS navigation message type nav_msgs::msg.

## Robot Localization

robot_localization (from <https://github.com/cra-ros-pkg/robot_localization>) is a collection of state estimation nodes, each of which is an implementation of a nonlinear state estimator for robots moving in 3D space. It contains two state estimation nodes, ekf_localization_node and ukf_localization_node. In addition, robot_localization provides navsat_transform_node, which aids in the integration of GPS data.

## Navigation 2

**Tutorials**: [Navigation](../tutorials_amr/navigation/index.md)

ROS 2 Navigation stack seeks a safe way to have a mobile robot move from point A to point B. This completes dynamic path planning, computes velocities for motors, detects and avoids obstacles, and structures recovery behaviors. Navigation 2 uses behavior trees to call modular servers to complete an action. An action can be computing a path, controlling effort, recovery, or any other navigation-related action. These are separate nodes that communicate with the behavior tree over a ROS 2 action server.
