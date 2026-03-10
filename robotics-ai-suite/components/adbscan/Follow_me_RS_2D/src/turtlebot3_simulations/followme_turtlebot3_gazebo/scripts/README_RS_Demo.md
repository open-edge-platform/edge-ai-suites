<!--
SPDX-FileCopyrightText: 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# RealSense Demo - 3 Terminal Setup

The RealSense mode uses a 3-terminal architecture for better control over initialization timing and easier debugging.

## Why 3 Terminals?

- **Terminal 1**: Gazebo + RViz + Bridges (sensor data & simulation)
- **Terminal 2**: ADBSCAN node (point cloud processing & target detection)
- **Terminal 3**: Gesture recognition + Trajectory control (guide robot control)

This separation allows proper initialization order and prevents timing issues.

## Quick Start

### Terminal 1: Launch Gazebo
```bash
cd Follow_me_RS_2D/src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts
./demo_RS.sh
```
**Wait for**: Gazebo GUI to fully load and robots to spawn

### Terminal 2: Launch ADBSCAN (after Gazebo is ready)
```bash
cd Follow_me_RS_2D/src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts
./demo_RS_terminal2.sh
```
**Wait for**: ADBSCAN node to start processing point clouds (~2-3 seconds)

### Terminal 3: Launch Gesture + Trajectory (after ADBSCAN is running)
```bash
cd Follow_me_RS_2D/src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts
./demo_RS_terminal3.sh
```

## What Happens

1. **0-10 seconds**: Guide robot stays still at x=0.8m showing Thumb_Up gesture
   - Point cloud bridge initializes
   - ADBSCAN detects guide robot
   - Waffle locks onto target

2. **10+ seconds**: Guide robot slowly moves forward (x: 0.8m → 1.5m)
   - Waffle follows while receiving Thumb_Up gesture
   - Guide stays within 1.5m max detection range

3. **When guide reaches x=1.5m**: Shows Thumb_Down and stops
   - Waffle receives stop command and halts

## Manual Commands (Alternative)

If you prefer not to use the helper scripts:

### Terminal 2

```bash
ros2 run adbscan_ros2_follow_me adbscan_sub_w_gesture --ros-args \
  --params-file $(ros2 pkg prefix adbscan_ros2_follow_me)/share/adbscan_ros2_follow_me/config/adbscan_sub_RS.yaml \
  -r cmd_vel:=tb3/cmd_vel
```

### Terminal 3

```bash
# Start gesture recognition (background)
ros2 run gesture_recognition_pkg gesture_recognition_node.py --ros-args \
  --params-file $(ros2 pkg prefix gesture_recognition_pkg)/share/gesture_recognition_pkg/config/gesture_recognition.yaml &

# Start trajectory publisher (foreground)
ros2 run gesture_recognition_pkg traj_and_img_publisher_node.py --ros-args \
  --params-file $(ros2 pkg prefix gesture_recognition_pkg)/share/gesture_recognition_pkg/config/gesture_recognition.yaml
```

## Key Differences from LIDAR Mode

- **LIDAR**: Single integrated launch (demo_lidar.sh launches everything)
- **RealSense**: 3-terminal manual startup for better initialization control

## Troubleshooting

**Waffle not following?**
1. Check point cloud data: `ros2 topic hz /camera/points` (should be ~9 Hz)
2. Check gesture: `ros2 topic echo /gesture` (should show Thumb_Up)
3. Check ADBSCAN output: `ros2 topic echo /tb3/cmd_vel` (should show velocity commands)
4. Restart in order: Terminal 1 → wait → Terminal 2 → wait → Terminal 3

**Bridge QoS issues?**
- The launch file sets BEST_EFFORT reliability for `/camera/points` to match ADBSCAN's subscription

**Guide robot moving in wrong direction?**
- RS mode uses X-based trajectory (forward along X-axis)
- LIDAR mode uses Y-based trajectory (different orientation)
