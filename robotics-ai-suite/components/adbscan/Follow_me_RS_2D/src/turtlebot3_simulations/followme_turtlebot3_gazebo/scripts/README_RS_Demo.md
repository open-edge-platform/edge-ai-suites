<!--
SPDX-FileCopyrightText: 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Gazebo Follow-Me Demo Scripts

This directory contains four single-terminal demo scripts for the
ADBSCAN follow-me application. Each script launches Gazebo Harmonic
(Jazzy) or Gazebo Fortress (Humble), all required ROS 2 nodes, the
Gazebo-ROS bridges, and RViz in **one terminal**.

## Demo Modes at a Glance

| Script | Sensor | Audio/TTS | ADBSCAN Executable | Launch Files |
|---|---|---|---|---|
| `demo_RS.sh` | Depth camera (RS) | No | `adbscan_sub_w_gesture` | `rs_shared.launch.py` + `rs_gesture.launch.py` |
| `demo_lidar.sh` | 2-D LiDAR | No | `adbscan_sub_w_gesture` | `lidar_shared.launch.py` + `lidar_gesture.launch.py` |
| `demo_RS_audio.sh` | Depth camera (RS) | Yes | `adbscan_sub_w_gesture_audio` | `rs_shared.launch.py` + `rs_gesture_audio.launch.py` |
| `demo_lidar_audio.sh` | 2-D LiDAR | Yes | `adbscan_sub_w_gesture_audio` | `lidar_shared.launch.py` + `lidar_gesture_audio.launch.py` |

## Prerequisites

```bash
# Build the workspace
cd <workspace_root>
colcon build --symlink-install
source install/setup.bash
```

Ensure `TURTLEBOT3_MODEL=waffle` is exported (the scripts set this
automatically).

## Quick Start

All scripts are in the same directory:

```bash
cd Follow_me_RS_2D/src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts
```

### RealSense (gesture only)

```bash
./demo_RS.sh
```

### 2-D LiDAR (gesture only)

```bash
./demo_lidar.sh
```

### RealSense + Audio/TTS

```bash
./demo_RS_audio.sh
```

### 2-D LiDAR + Audio/TTS

```bash
./demo_lidar_audio.sh
```

## Architecture

### Non-Audio Demos (`demo_RS.sh` / `demo_lidar.sh`)

A two-phase launch in one terminal (3 steps):

1. **Shared launch** (`rs_shared.launch.py` or `lidar_shared.launch.py`)
   — Gazebo world, robot spawns, Gazebo-ROS bridges
2. *(15 s wait for Gazebo to initialize)*
3. **Perception launch** (`rs_gesture.launch.py` or
   `lidar_gesture.launch.py`) — ADBSCAN node, gesture recognition,
   trajectory & image publisher
4. **RViz** — opened in the foreground

Nodes started by the perception launch:

- **ADBSCAN** — `adbscan_sub_w_gesture` (target detection and `cmd_vel`
  generation)
- **Gesture recognition** — `gesture_recognition_node.py` (simulated
  gesture classification via MediaPipe)
- **Trajectory & image publisher** — `traj_and_img_publisher_node.py`
  (guide-robot waypoints + simulated camera images)

### Audio Demos (`demo_RS_audio.sh` / `demo_lidar_audio.sh`)

A four-step startup in one terminal:

1. **Text-to-speech node** — `text_to_speech_node.py` (TTS via Forward
   Tacotron + MelGAN, OpenVINO)
2. **Shared launch** (`rs_shared.launch.py` or `lidar_shared.launch.py`)
   — Gazebo world, robot spawns, Gazebo-ROS bridges
3. *(15 s wait for Gazebo to initialize)*
4. **Perception launch** (`rs_gesture_audio.launch.py` or
   `lidar_gesture_audio.launch.py`) — ADBSCAN node (gesture + audio),
   gesture recognition, speech recognition (QuartzNet via OpenVINO),
   trajectory publisher, and audio file publisher
5. **RViz** — opened in the foreground

## Launch Files

| Launch File | Phase | Description |
|---|---|---|
| `lidar_shared.launch.py` | Shared | Gazebo world + bridges for 2D LiDAR (stock waffle model) |
| `rs_shared.launch.py` | Shared | Gazebo world + bridges for depth camera (`waffle_depth` model) |
| `lidar_gesture.launch.py` | Perception | ADBSCAN + gesture + trajectory (LiDAR, no audio) |
| `lidar_gesture_audio.launch.py` | Perception | ADBSCAN + gesture + speech + audio + trajectory (LiDAR) |
| `rs_gesture.launch.py` | Perception | ADBSCAN + gesture + trajectory (RS, with Gazebo sim overrides) |
| `rs_gesture_audio.launch.py` | Perception | ADBSCAN + gesture + speech + audio + trajectory (RS, with Gazebo sim overrides) |

### Gazebo Simulation Parameter Overrides (RS only)

The RealSense perception launch files override three ADBSCAN parameters
for the simulated depth camera:

| Parameter | YAML Default | Sim Override | Reason |
|---|---|---|---|
| `optical_frame` | `true` | `false` | Gazebo publishes PointCloud2 in body frame, not optical frame |
| `min_dist` | `0.5` | `0.3` | Guide robot surface appears at ~0.44 m in sim (below YAML threshold) |
| `init_tgt_loc` | `0.8` | `0.5` | Matches actual cluster centroid distance in sim |

These overrides are **not** needed on real hardware with an Intel
RealSense camera.

## Gazebo-ROS Bridges

Because Gazebo Harmonic uses a separate transport layer, every topic
exchanged between Gazebo and ROS 2 requires an explicit
`ros_gz_bridge` node. The bridges started by each launch configuration
are listed below.

| Bridge | Topic | Direction | RS | LiDAR | Audio |
|---|---|---|---|---|---|
| Clock | `/clock` | Gz → ROS 2 | Yes | Yes | Yes |
| LiDAR scan | `/scan` | Gz → ROS 2 | — | Yes | Yes |
| Point cloud | `/camera/points` | Gz → ROS 2 | Yes | — | Yes |
| Camera image | `/camera/image_raw` | Gz → ROS 2 | Yes | Yes | Yes |
| Follower cmd\_vel | `/tb3/cmd_vel` | ROS 2 → Gz | Yes | Yes | Yes |
| Guide cmd\_vel | `/guide_robot/cmd_vel` | ROS 2 → Gz | Yes | Yes | Yes |
| Guide odometry | `/guide_robot/odom` | Gz → ROS 2 | Yes | Yes | Yes |

> **Note:** The `/camera/points` bridge uses `best_effort` QoS to match
> the ADBSCAN subscriber.

## Key Differences Between RS and LiDAR Modes

| | RealSense (RS) | 2-D LiDAR |
|---|---|---|
| Sensor topic | `/camera/points` (`PointCloud2`) | `/scan` (`LaserScan`) |
| ADBSCAN config | `adbscan_sub_RS.yaml` | `adbscan_sub_2D.yaml` |
| Subsample ratio | 15–30 | 2 |
| Waffle model | `turtlebot3_waffle_depth` (custom RGBD SDF) | Stock `turtlebot3_waffle` |
| Scale factor | 0.9 | 0.07 |

## Troubleshooting

### Waffle not following the guide robot?

1. **Check sensor data:**
   - RS: `ros2 topic hz /camera/points` (expect ~9 Hz)
   - LiDAR: `ros2 topic hz /scan`
2. **Check gesture:** `ros2 topic echo /gesture` (expect `Thumb_Up`)
3. **Check ADBSCAN output:** `ros2 topic echo /tb3/cmd_vel`
4. If topics show 0 publishers, verify the Gazebo-ROS bridge nodes are
   running: `ros2 node list | grep bridge`

### Camera image not showing in RViz?

- Verify data is flowing: `ros2 topic hz /camera/image_raw`
- The bridge subscribes to the Gazebo-side `/camera/image_raw` topic.
  Confirm it exists: `gz topic -l | grep camera`

### Bridge QoS mismatch?

The `/camera/points` bridge uses `best_effort` reliability. If your
subscriber expects `reliable`, no data will flow. Check with:

```bash
ros2 topic info /camera/points --verbose
```

### Audio demo: no speech commands reaching ADBSCAN?

- Confirm the TTS node is running: `ros2 node list | grep text_to_speech`
- Check audio file publisher: `ros2 topic echo /audio_filename`
- Check speech recognition output: `ros2 topic echo /audio_command`
- Ensure OpenVINO model files are present (see
  `text_to_speech_config.yaml` and `speech_recognition.yaml` for paths)
- The speech recognition node skips empty filenames and holds valid
  commands ("start"/"stop") for 3 seconds before decaying to "no_action"
