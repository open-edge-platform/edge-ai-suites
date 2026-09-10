# Deploying `wandering` on Clearpath Jackal

This software reference details how to deploy and run the `wandering` mobile robot application on a Clearpath Robotics Jackal robot upgraded with an Intel® Core™ Ultra Series 3 "Panther Lake" (PTL) onboard compute board (e.g., Intel Core Ultra X7 358H reference platform).

The pipeline combines Intel® RealSense™ depth camera sensing, RTAB-Map visual SLAM, multi-sensor point cloud fusion (`adbscan_sensor_fusion`), fast 3D clustering obstacle perception (`adbscan_ros2`), Nav2 navigation with custom costmap layers (`nav2_adbscan_layer`), and autonomous frontier exploration (`wandering_app`).

## Architecture

The Panther Lake onboard compute board handles on-robot perception, SLAM, costmap marking, and autonomous navigation:

```{mermaid}
flowchart TD
    subgraph Hardware["Onboard Hardware (Clearpath Jackal + Panther Lake)"]
        RS["Intel® RealSense™ Camera\n(RGB-D PointCloud2 & Depth)"]
        LiDAR3D["360° 3D LiDAR (e.g. Velodyne Puck)\n(PointCloud2)"]
        BaseServices["Clearpath Base Services / MCU\n(Encoders, IMU, Teleop Mux)"]
    end

    subgraph Perception["Onboard Perception & SLAM (Panther Lake)"]
        D2L["depthimage_to_laserscan\n(/scan)"]
        Fusion["adbscan_sensor_fusion\n(Time-sync & Voxel filter)"]
        ADBSCAN["ADBSCAN Node\n(3D Clustering)"]
        RTAB["RTAB-Map Visual SLAM\n(RGB-D Mapping & TF)"]
    end

    subgraph Navigation["Nav2 Navigation Stack"]
        Costmap["Nav2 Costmaps\n(ADBScanLayer + Standard Layers)"]
        NavServer["Nav2 Planner & Controller\n(FollowPath, Recovery)"]
    end

    subgraph Application["wandering_app Package"]
        WanderApp["wandering_app\n(Frontier Exploration)"]
    end

    RS --> D2L
    RS -.->|"Default point cloud"| Fusion
    LiDAR3D -.->|"Alternative 360° cloud"| Fusion
    D2L --> Fusion
    RS --> RTAB
    D2L --> RTAB
    Fusion -->|"/adbscan/points"| ADBSCAN
    ADBSCAN -->|"/obstacle_array"| Costmap
    RTAB -->|"/map & TF"| Navigation
    BaseServices -->|"odom, TF"| Navigation
    Costmap --> NavServer
    Costmap -->|"/global_costmap/costmap"| WanderApp
    WanderApp -->|"NavigateToPose action"| NavServer
    NavServer -->|"/cmd_vel"| BaseServices
```

### Perception and Navigation Pipeline

1. **Depth Sensing & 2D Scan Derivation**: The onboard Intel RealSense camera provides depth and color streams. The `depthimage_to_laserscan` node projects depth images into a 2D `/scan` topic used for SLAM and base obstacle clearing.
2. **Visual SLAM**: `dep_rtabmap_jackal` runs RTAB-Map visual SLAM with RGB-D synchronization, producing real-time 3D and 2D occupancy mapping, loop closure, and the `map` $\rightarrow$ `odom` coordinate frame transform.
3. **Sensor Fusion**: `adbscan_sensor_fusion` time-synchronizes the 2D scan and 3D point cloud (from either the RealSense camera or an optional 360° 3D LiDAR such as a Velodyne Puck), transforms them into the `base_link` frame, and applies voxel downsampling to generate `/adbscan/points`.
4. **3D Obstacle Perception**: `adbscan_ros2` executes 3D density-based spatial clustering on `/adbscan/points`, detecting object-sized obstacles and publishing `nav2_dynamic_msgs/ObstacleArray` messages on `/obstacle_array`.
5. **Nav2 Costmap Integration**: `nav2_adbscan_layer::ADBScanLayer` integrates into both local and global Nav2 costmaps, marking lethal circular obstacle regions based on `/obstacle_array` with configurable radius padding and detection lifetime.
6. **Autonomous Frontier Exploration**: `wandering_app` (`wandering_mapper` node) continuously evaluates the global costmap for unexplored frontiers and issues `NavigateToPose` goals to Nav2.

## Prerequisites

Before deploying the pipeline:

1. **Hardware Setup**: Follow the [Clearpath Robotics Jackal setup](../../../hardware_blueprints/amr/clearpath-jackal.md) guide to install the Panther Lake onboard compute board, mount and connect the Intel RealSense camera (e.g. D435i), and configure the robot network and MCU firmware.
2. **Clearpath Base Services**: Verify that the Clearpath systemd services (`clearpath-platform.service`, `clearpath-sensors.service`, `clearpath-robot.service`) are active and publishing topics under the robot's namespace.
3. **Motor Control**: Verify motor control and drive commands following the [Validate Motor Control](../../../hardware_blueprints/amr/clearpath-jackal.md#validate-motor-control) section.
4. **Target Environment**: Ensure Ubuntu 24.04 LTS with ROS 2 Jazzy (or Ubuntu 22.04 LTS with ROS 2 Humble) is installed on the Panther Lake board along with OpenVINO™ packages and Intel® NPU drivers (if applicable for Intel Core Ultra).

## Install the Application

Install the `wandering` metapackage for your installed ROS 2 distribution:

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
sudo apt update
sudo apt install ros-jazzy-wandering
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
sudo apt update
sudo apt install ros-humble-wandering
```

:::
::::

If building from source, build the application using the `make build` target:

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
ROS_DISTRO=jazzy make build
source install/setup.bash
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
ROS_DISTRO=humble make build
source install/setup.bash
```

:::
::::

## Run the Deployment

### Configure the Robot Namespace

Clearpath Jackal base services publish transforms and topics under a robot namespace (default: `/j100_0812`). Set the `ROBOT_NAMESPACE` environment variable to match your robot's configured namespace in `/etc/clearpath/robot.yaml`:

```bash
export ROBOT_NAMESPACE=/j100_0812
```

### Autonomous Exploration Mode (Default: Intel RealSense Depth Sensing)

Launch the complete autonomous pipeline using the RealSense depth camera:

```bash
export ROBOT_NAMESPACE=/j100_0812
ros2 launch wandering_bringup wandering_jackal.launch.py
```

**What this starts:**

1. `depthimage_to_laserscan`: Derives 2D `/scan` from the RealSense depth image.
2. `dep_rtabmap_jackal`: Starts RTAB-Map visual SLAM and RGB-D synchronization.
3. `dep_navigation_jackal`: Starts the Jackal Nav2 stack configured with `ADBScanLayer` in both local and global costmaps.
4. `dep_adbscan_perception`: Fuses the scan and RealSense point cloud, performs 3D ADBSCAN obstacle clustering, and publishes `/obstacle_array`.
5. `wandering_app`: Frontier-exploration node (`wandering_mapper`) that evaluates unexplored frontiers on the costmap and sends `NavigateToPose` goals to Nav2.
6. RViz visualization windows (when a display session or remote X11 forwarding is available).

After startup, the robot begins autonomously exploring its surroundings, mapping the environment while avoiding obstacles.

![wandering-jackal-rviz2](images/wandering-jackal-rviz2.png)

To stop the pipeline, press `Ctrl-c` in the launch terminal.

### Alternative Launch Path: 360-Degree 3D LiDAR (Velodyne Puck) Input

When the Jackal robot is equipped with a 360-degree 3D LiDAR (such as a Velodyne Puck VLP-16, Ouster OS1, or equivalent 3D LiDAR), you can route the full 360-degree point cloud directly into the ADBSCAN perception pipeline as an alternative to the forward-facing RealSense depth camera point cloud.

**How perception behaves in this path:**

- `adbscan_sensor_fusion` transforms the 360-degree LiDAR cloud into `base_link`, crops it to the robot's near-field driveable envelope, filters out floor-level returns, and voxel-downsamples the points before streaming them on `/adbscan/points`.
- The Velodyne preset intentionally does **not** append planar `/scan` points into this 3D point cloud; this avoids planar scan returns bridging distinct 3D objects into single oversized clusters. The 2D `/scan` topic remains independently active and continuously fed to RTAB-Map SLAM, standard Nav2 obstacle clearing layers, and collision monitoring.
- `adbscan_ros2` clusters the filtered 360-degree cloud in 3D mode, publishing detected object-sized 3D obstacles around the robot to `/obstacle_array`.

**Step 1: Identify and verify the streaming 3D LiDAR topic and frame**

Common Clearpath topic names for 3D LiDAR point clouds include `/sensors/lidar3d_0/points` or `/velodyne_points`. Check that your robot's LiDAR driver service is actively streaming data by monitoring the publication rate:

```bash
ros2 topic hz /sensors/lidar3d_0/points
# or if using /velodyne_points:
ros2 topic hz /velodyne_points
```

Confirm that the header frame resolves to `base_link` through the robot's namespaced TF tree:

```bash
ros2 topic echo --once /sensors/lidar3d_0/points header
ros2 run tf2_ros tf2_echo base_link <lidar_frame_id>
```

**Step 2: Launch with the 3D LiDAR configuration preset**

Pass the prepared Velodyne parameter presets and point cloud topic override:

```bash
export ROBOT_NAMESPACE=/j100_0812
export LIDAR3D_TOPIC=/sensors/lidar3d_0/points

ros2 launch wandering_bringup wandering_jackal.launch.py \
  fusion_params_file:=$(ros2 pkg prefix wandering_bringup)/share/wandering_bringup/params/pointcloud_fusion_jackal_velodyne.yaml \
  adbscan_params_file:=$(ros2 pkg prefix wandering_bringup)/share/wandering_bringup/params/adbscan_velodyne.yaml \
  pointcloud_topic:=$LIDAR3D_TOPIC
```

The stack starts up with full 360-degree obstacle clustering around the robot while maintaining visual SLAM mapping and autonomous frontier exploration.

### Interactive Manual Override Mode & Nav2 Waypointing

To retain autonomous SLAM mapping and ADBSCAN costmap protection while allowing an operator to pause exploration and send manual navigation goals or multi-stop waypoint routes via RViz:

```bash
export ROBOT_NAMESPACE=/j100_0812
ros2 launch wandering_bringup wandering_jackal_manual_nav.launch.py
```

- **Pausing Autonomous Exploration**: In the RViz interface, click **Manual mode** in the **Wandering Control** panel to pause autonomous frontier exploration and cancel the active goal.
- **Single-Goal Navigation**: Use Nav2's **Nav2 Goal** (or **2D Goal Pose**) tool in the RViz toolbar to click and drag a custom destination pose (position and orientation) on the map. Nav2 computes and follows a path while the `ADBScanLayer` continues updating obstacle regions around the robot.
- **Nav2 Waypoint Following**: Switch Nav2 to **Waypoint mode** in the RViz Nav2 panel, click and place a sequence of goal poses across the mapped facility, and select **Start Navigation** to command the robot through all waypoints in order.
- **Resuming Autonomous Exploration**: Click **Autonomous mode** in the **Wandering Control** panel to resume autonomous frontier wandering.

> **Note:** The manual override launch file accepts the same `fusion_params_file`, `adbscan_params_file`, and `pointcloud_topic` arguments if you want to use the 360-degree LiDAR profile with interactive operator goals.

### Standard 2D LiDAR Nav2 (without ADBSCAN)

To run the standard 2D Nav2 pipeline without the ADBSCAN fusion and clustering nodes:

```bash
ros2 launch wandering_bringup wandering_jackal.launch.py enable_adbscan:=false
```

## Perception Pipeline Tuning & Configuration Options

The perception pipeline is composed of three interconnected stages: point cloud fusion and ground removal (`adbscan_sensor_fusion`), 3D density-based obstacle clustering (`adbscan_ros2`), and costmap marking (`nav2_adbscan_layer`). Tuning parameters across these stages allows optimizing obstacle detection sensitivity, cluster sizes, and false-positive rejection for different sensors and robot environments.

### 1. Point Cloud Fusion & Filtering (`adbscan_sensor_fusion`)

Configured via `pointcloud_fusion_jackal.yaml` (RealSense) or `pointcloud_fusion_jackal_velodyne.yaml` (3D LiDAR). This node prepares and cleans point clouds before passing them to ADBSCAN:

| Parameter | Default (RealSense / Velodyne) | Description & Tuning Impact |
| :--- | :--- | :--- |
| `voxel_leaf_size` | `0.03` m / `0.05` m | Edge length of the 3D voxel grid filter. Larger values downsample more aggressively, reducing downstream clustering computation and clustering latency on dense sensors; smaller values preserve fine geometric details of small obstacles. |
| `min_range` / `max_range` | `0.0` m / `0.40` m – `3.00` m | Radial distance cropping bounds relative to `base_link`. For 360° LiDAR, setting `max_range: 3.0` focuses clustering within the robot's immediate planning envelope and caps processing load. |
| `min_z` / `max_z` | Unbounded / `-0.35` m – `1.50` m | Height window (metres) in `base_link` coordinates. Excludes returns from ceilings or overhead structures above the robot while keeping points from the floor plane upwards. |
| `remove_ground` | `false` / `true` | Enables RANSAC planar ground segmentation. Essential for 3D LiDAR sensors whose lowest rings intersect the ground. |
| `ground_distance_threshold` | `0.08` m | Distance threshold in metres for points classified as ground plane inliers. Points closer than this to the estimated ground plane are stripped away. |
| `ground_max_tilt_degrees` | `12.0` deg | Maximum tilt angle allowed for the estimated ground plane normal. Prevents steep walls from being erroneously classified as ground. |
| `sync_max_interval` | `0.1` s | Maximum allowed timestamp skew when synchronizing 2D scan and 3D point cloud topics. |

### 2. 3D Spatial Clustering (`adbscan_ros2`)

Configured via `adbscan_fused.yaml` (RealSense) or `adbscan_velodyne.yaml` (Velodyne Puck). These parameters dictate how points are clustered into distinct obstacles:

| Parameter | Default (Fused / Velodyne) | Description & Tuning Impact |
| :--- | :--- | :--- |
| `x_filter_back` | `4.0` m / `2.5` m | Maximum distance behind the robot (in metres) to include points for obstacle clustering. |
| `y_filter_left` / `y_filter_right` | `3.0` m, `-3.0` m / `1.75` m, `-1.75` m | Lateral region-of-interest bounds (metres) to the left and right of the robot's longitudinal centerline. |
| `subsample_ratio` | `1.0` / `2.0` | Subsampling ratio applied to incoming points before clustering. A ratio of `2.0` clusters every second point, halving density to speed up clustering on dense clouds. |
| `scale_factor` | `0.20` | Scaling coefficient for density-adaptive clustering radius calculation. Lower values enforce tighter clusters; higher values allow sparser, wider clusters to merge. |
| `min_3d_epsilon` | `0.15` m | Minimum neighborhood radius ($\epsilon$) in metres for a point to be linked to an adjacent point in 3D clustering. Increase if sparse sensor returns fragment single objects into separate clusters; decrease if nearby objects bridge across empty space. |
| `base`, `coeff_1`, `coeff_2` | Adaptive polynomial | Quadratic distance-adaptive coefficients ($r = \text{base} + \text{coeff}_1 \cdot d + \text{coeff}_2 \cdot d^2$) that scale clustering radius as a function of object distance $d$. Accounts for angular divergence in LiDAR beams or camera depth dispersion at greater ranges. |
| `z_filter` / `Z_based_ground_removal` | `-0.15` m / `1.0` | Secondary floor height gate to discard points beneath floor level in `base_link` frame. |

### 3. Costmap Marking & Obstacle Bounds (`nav2_adbscan_layer`)

Configured under `local_costmap` and `global_costmap` in `jackal_nav_adbscan.param.yaml`. Controls how ADBSCAN clusters are stamped into Nav2 costmaps:

| Parameter | Default | Description & Tuning Impact |
| :--- | :--- | :--- |
| `min_mark_radius` | `0.04` m | Minimum circular lethal marking radius in metres stamped into the costmap, guaranteeing that even thin objects (e.g. table legs or cables) receive non-zero lethal clearance. |
| `footprint_padding` | `0.05` m | Extra buffer distance (metres) added around the perimeter of the detected obstacle cluster. |
| `max_obstacle_extent` | `2.5` m | Maximum allowed bounding box dimension (metres) for a valid obstacle. Clusters exceeding this size (such as large continuous walls or unsegmented floor patches) are rejected from dynamic layer marking to avoid overwriting static map features. |
| `max_detection_distance` | `3.0` m (local) / `4.0` m (global) | Maximum distance from the robot at which obstacle detections will be committed to the costmap. Prevents distant, noisy detections from degrading local path planning. |
| `time_to_live` | `0.5` s (local) / `1.0` s (global) | Duration (seconds) that an obstacle remains marked in the costmap after being detected. Once this time elapses without a new detection update, the obstacle is cleared. Keeps the costmap responsive to dynamic environments. |

## Advanced Configuration

### Persistent RTAB-Map Database

To preserve or extend an existing RTAB-Map SLAM database across multiple sessions, specify a database file path:

```bash
ros2 launch wandering_bringup wandering_jackal.launch.py \
  rtabmap_database_path:=/data/maps/site_jackal.db
```

### Velocity Command Stamping (Twist vs TwistStamped)

Depending on your robot's Clearpath base driver version and ROS 2 distribution:

- Set `enable_stamped_cmd_vel: true` in the Nav2 parameter file (`jackal_nav_adbscan.param.yaml`) when the platform driver or teleop multiplexer accepts `geometry_msgs/msg/TwistStamped`.
- Set `enable_stamped_cmd_vel: false` for unstamped `geometry_msgs/msg/Twist` drivers.
- If adapting mismatched driver types, the `twist_stamper` ROS 2 package can convert between `Twist` and `TwistStamped` topics.

To inspect the velocity topic expected by your robot:

```bash
ros2 topic info /${ROBOT_NAMESPACE#/}/cmd_vel -v
```

### Camera Topic Overrides

If your RealSense camera is configured with custom topic names, override them at launch:

```bash
ros2 launch wandering_bringup wandering_jackal.launch.py \
  camera_namespace:=/sensors/camera_0 \
  depth_image_topic:=/sensors/camera_0/camera/depth/image_rect_raw \
  rgb_image_topic:=/sensors/camera_0/camera/color/image_raw
```

## Troubleshooting

### 1. Robot Does Not Move Despite Active Exploration Goals

- **Symptom**: `wandering_app` picks frontiers and sends `NavigateToPose` goals to Nav2, but the robot remains stationary.
- **Root Cause**: Stamped vs. unstamped velocity command mismatch between Nav2 and the Clearpath base multiplexer (`twist_mux`), or an incorrect topic namespace.
- **Verification**:
  Check what message type the robot's base controller is subscribing to:
  ```bash
  ros2 topic info /cmd_vel -v
  # or under the robot namespace:
  ros2 topic info /${ROBOT_NAMESPACE#/}/cmd_vel -v
  ```
- **Remedy**:
  - If the base driver expects unstamped `geometry_msgs/msg/Twist`, set `enable_stamped_cmd_vel: false` under `controller_server` in `jackal_nav_adbscan.param.yaml`.
  - If the base driver expects `geometry_msgs/msg/TwistStamped`, set `enable_stamped_cmd_vel: true`.
  - Alternatively, use the `twist_stamper` ROS 2 node to bridge unstamped and stamped velocity topics.

### 2. Missing RealSense Point Cloud (`/sensors/camera_0/points` Not Publishing)

- **Symptom**: `adbscan_pointcloud_fusion` waits indefinitely without publishing `/adbscan/points`, even though camera image topics are active.
- **Root Cause**: The RealSense camera ROS 2 driver was launched without point cloud generation enabled, or the USB connection fell back to USB 2.0.
- **Verification**:
  ```bash
  ros2 topic hz /sensors/camera_0/points
  lsusb -t | grep -i uvcvideo
  ```
- **Remedy**:
  - In `/etc/clearpath/robot.yaml` under the camera device parameters, ensure `pointcloud.enable: true` is configured.
  - Verify that the camera is plugged into a USB 3.0 / 3.1 port providing SuperSpeed (5000M) throughput. USB 2.0 connections lack sufficient bandwidth for simultaneous RGB, depth, and point cloud streams.

### 3. Sensor Fusion Synchronization Dropouts (`adbscan_sensor_fusion`)

- **Symptom**: Warning logs indicating dropped messages or timestamp skew in `adbscan_pointcloud_fusion`.
- **Root Cause**: The approximate-time message synchronizer cannot pair RealSense depth point clouds and derived `/scan` frames within the skew tolerance window (`sync_max_interval`).
- **Remedy**:
  In `pointcloud_fusion_jackal.yaml`, increase the synchronizer queue and tolerance window:
  ```yaml
  sync_queue_size: 30
  sync_max_interval: 0.20
  ```

### 4. Floor Returns Clustered as Ghost Obstacles

- **Symptom**: The robot stops or oscillates in place because lethal costmap obstacles are falsely marked on the clear floor directly in front of the robot.
- **Root Cause**: Camera pitch angle deflection, vehicle chassis pitch under acceleration, or floor points falling above the ground filter cutoff.
- **Verification**:
  Echo `/obstacle_array` or inspect RViz `/adbscan/obstacle_markers` to verify if obstacles have $z \approx 0$:
  ```bash
  ros2 topic echo /obstacle_array --once
  ```
- **Remedy**:
  - Adjust the height cutoff `z_filter: -0.10` in `adbscan_fused.yaml` (or `min_z` in the fusion parameter file).
  - For 3D LiDAR deployments, verify that `remove_ground: true` is active and tune `ground_distance_threshold` (e.g. `0.08` m to `0.10` m) and `ground_max_tilt_degrees`.

### 5. Namespaced TF Lookup Failures

- **Symptom**: Nodes log errors like `ExtrapolationException` or `Could not transform from camera_0_link to base_link`.
- **Root Cause**: Clearpath Jackal publishes TF transforms under `/<robot_namespace>/tf` and `/<robot_namespace>/tf_static`. If `ROBOT_NAMESPACE` is unset or mismatched, nodes listen on the root `/tf` topic instead.
- **Verification**:
  ```bash
  echo $ROBOT_NAMESPACE
  ros2 topic list | grep tf
  ros2 run tf2_tools view_frames
  ```
- **Remedy**:
  Export `ROBOT_NAMESPACE` to match the exact prefix defined in `/etc/clearpath/robot.yaml` (e.g. `export ROBOT_NAMESPACE=/j100_0812`) before executing any launch commands.

### 6. High Perception Latency or Stuttering on 360-Degree LiDAR

- **Symptom**: Laggy costmap updates, delayed obstacle avoidance, or high CPU utilization during 3D clustering.
- **Root Cause**: Raw 3D point cloud is overly dense or the spatial region of interest is excessively large for real-time clustering.
- **Remedy**:
  - Increase `voxel_leaf_size` in `pointcloud_fusion_jackal_velodyne.yaml` from `0.05` to `0.07` or `0.08`.
  - Increase `subsample_ratio` in `adbscan_velodyne.yaml` from `1.0` to `2.0` or `3.0`.
  - Reduce `max_range` in the fusion parameters (e.g., to `2.5` m) to restrict clustering to the immediate driveable envelope.

### General Troubleshooting

- **No topics visible**: Verify that the `ROS_DOMAIN_ID` environment variable matches the `domain_id` configured in `/etc/clearpath/robot.yaml`.
- **Missing sensor topics**: Check the status of the Clearpath systemd services:
  ```bash
  sudo systemctl status clearpath-platform.service clearpath-sensors.service clearpath-robot.service
  ```
- For general system issues, refer to the [troubleshooting guide](../../../resources/troubleshooting.md).

## Next Steps

Now that you've deployed the `wandering` workflow on physical hardware:

- Visit [Optimized Solutions](../../../components/optimized_solutions/index.md) to explore further AMR-specific components, including OpenVINO™-accelerated workloads.
- See the [Clearpath Robotics Jackal blueprint](../../../hardware_blueprints/amr/clearpath-jackal.md) for more hardware configuration details.