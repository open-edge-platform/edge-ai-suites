<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Intel's Robotics AI Suite: Follow-Me with Gesture and Audio Control

A Gazebo simulation of a TurtleBot3 Waffle autonomously following a guide robot using Intel's
ADBSCAN (Adaptive DBSCAN) algorithm. Supports two sensor modes — 2D LiDAR and Intel RealSense
depth camera — with optional hand-gesture control and voice audio control.

## Demo Modes

| Mode | Sensor | Gesture | Audio | Script |
|------|--------|---------|-------|--------|
| LiDAR + Gesture | 2D LiDAR | Yes | No | `demo_lidar.sh` |
| LiDAR + Gesture + Audio | 2D LiDAR | Yes | Yes | `demo_lidar_audio.sh` |
| RealSense + Gesture | Depth camera | Yes | No | `demo_RS.sh` |
| RealSense + Gesture + Audio | Depth camera | Yes | Yes | `demo_RS_audio.sh` |

---

## Prerequisites

### Supported ROS 2 Distributions

| ROS 2 | Gazebo | Status |
|-------|--------|--------|
| Jazzy | Harmonic | Recommended |
| Humble | Fortress | Supported |

### System Packages

```bash
sudo apt install python3-colcon-common-extensions python3-pip
# For ROS 2 Humble only:
sudo apt install ros-humble-gazebo-* ros-humble-dynamixel-sdk \
    ros-humble-turtlebot3-msgs ros-humble-turtlebot3 ros-humble-xacro
```

### Python Virtual Environment

Create a virtual environment **outside** the colcon workspace to avoid build interference:

```bash
sudo apt install pipx
pipx install virtualenv
pipx ensurepath
source ~/.bashrc

# Create venv (example location):
virtualenv ~/followme_env
source ~/followme_env/bin/activate
```

### Python Packages

This application uses the [MediaPipe Hands Framework](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html)
for hand gesture recognition.

For ROS 2 **Jazzy** (gesture only):
```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_jazzy.txt
```

For ROS 2 **Jazzy** (gesture + audio):
```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_jazzy.txt
pip3 install librosa openvino==2025.3.0 simpleaudio sounddevice tqdm inflect
```

For ROS 2 **Humble** (gesture only):
```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_humble.txt
```

For ROS 2 **Humble** (gesture + audio):
```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_humble.txt
pip3 install librosa openvino==2025.3.0 simpleaudio sounddevice tqdm inflect
```

---

## Build

```bash
cd Follow_me_RS_2D
source /opt/ros/<distro>/setup.bash
source ~/followme_env/bin/activate
colcon build --symlink-install
source install/setup.bash
```

---

## Running the Demos

All demo scripts auto-detect the installed ROS 2 distribution, source the workspace, kill any
stale Gazebo processes, and launch the full stack (Gazebo, ROS-Gazebo bridges, ADBSCAN, gesture,
trajectory, and optionally audio nodes) with RViz.

### 2D LiDAR — Gesture only

```bash
source ~/followme_env/bin/activate
./src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/demo_lidar.sh
```

### 2D LiDAR — Gesture + Audio

```bash
source ~/followme_env/bin/activate
./src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/demo_lidar_audio.sh
```

### RealSense — Gesture only

```bash
source ~/followme_env/bin/activate
./src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/demo_RS.sh
```

### RealSense — Gesture + Audio

```bash
source ~/followme_env/bin/activate
./src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/demo_RS_audio.sh
```

> **Note:** Allow ~10 seconds after launch for Gazebo and all nodes to initialize before the
> TurtleBot3 begins following. The guide robot trajectory runs for ~45 seconds.

---

## Architecture

Each demo runs in a single terminal using a two-phase launch sequence:

1. **Shared launch** (`*_shared.launch.py`) — Gazebo world, robot state publishers,
   Gazebo↔ROS bridges, and spawn of both the TurtleBot3 Waffle and guide robot.
2. **Perception launch** (`*_gesture.launch.py` or `*_gesture_audio.launch.py`) — ADBSCAN
   node, gesture recognition, trajectory publisher, and (for audio modes) speech recognition
   and audio file publisher.

### Launch Files

| Launch File | Phase | Description |
|-------------|-------|-------------|
| `lidar_shared.launch.py` | 1 | Gazebo world + bridges for 2D LiDAR |
| `rs_shared.launch.py` | 1 | Gazebo world + bridges for depth camera |
| `lidar_gesture.launch.py` | 2 | ADBSCAN + gesture + trajectory (LiDAR) |
| `lidar_gesture_audio.launch.py` | 2 | ADBSCAN + gesture + audio + trajectory (LiDAR) |
| `rs_gesture.launch.py` | 2 | ADBSCAN + gesture + trajectory (RS) |
| `rs_gesture_audio.launch.py` | 2 | ADBSCAN + gesture + audio + trajectory (RS) |

```text
                 ┌─────────────────────────────────────────────┐
                 │          Gazebo Harmonic / Fortress           │
                 │  ┌─────────────┐     ┌──────────────────┐   │
                 │  │ Guide Robot │────▶│ TurtleBot3 Waffle │   │
                 │  │ (traj node) │     │ (ADBSCAN follower)│   │
                 │  └─────────────┘     └──────────────────┘   │
                 └───────────┬─────────────────────────────────┘
                             │ /camera/points  OR  /scan
                             ▼
                  ┌─────────────────────┐
                  │     ADBSCAN Node    │  ◀── gesture_recognition_node
                  │  adbscan_sub_w_     │  ◀── speech_recognition_node (audio modes)
                  │  gesture[_audio]    │
                  └──────────┬──────────┘
                             │ /tb3/cmd_vel
                             ▼
                     TurtleBot3 Waffle
```

### Key Nodes

| Node | Package | Description |
|------|---------|-------------|
| `adbscan_sub_w_gesture` | `adbscan_ros2_follow_me` | ADBSCAN follower (gesture mode) |
| `adbscan_sub_w_gesture_audio` | `adbscan_ros2_follow_me` | ADBSCAN follower (gesture + audio) |
| `gesture_recognition_node.py` | `gesture_recognition_pkg` | MediaPipe hand gesture classifier |
| `traj_and_img_publisher_node.py` | `gesture_recognition_pkg` | Guide robot trajectory publisher |
| `speech_recognition_node.py` | `speech_recognition_pkg` | Voice command recognizer |
| `audio_publisher_node.py` | `speech_recognition_pkg` | Audio file publisher |

---

## Key Configuration Parameters

### Sensor Config Files

| Sensor | Config File |
|--------|-------------|
| 2D LiDAR | `src/adbscan_ros2/config/adbscan_sub_2D.yaml` |
| RealSense | `src/adbscan_ros2/config/adbscan_sub_RS.yaml` |

### Important Parameters

| Parameter | Description | Recommended Value |
|-----------|-------------|-------------------|
| `tracking_radius` | Search radius (m) around last known target each frame | `1.0` |
| `init_tgt_loc` | Initial target distance (m) the follower aims to maintain | `0.8` (hardware) / `0.5` (Gazebo sim) |
| `max_dist` | Maximum follow distance (m) — no command if guide is farther | `3.0` |
| `min_dist` | Minimum follow distance (m) — slow/stop when guide is closer | `0.5` (hardware) / `0.3` (Gazebo sim) |
| `max_linear` | Maximum linear velocity (m/s) | `0.8` |
| `max_angular` | Maximum angular velocity (rad/s) | `0.6` |
| `max_frame_blocked` | Frames without detection before target is considered lost | `5` |
| `z_filter` | Minimum Z height (m) for RS point cloud — filters ground | `-0.15` |
| `subsample_ratio` | Keep 1 in N points (RS point cloud subsampling) | `15.0` |
| `gesture_enable` | Enable hand gesture start/stop control | `true` |
| `audio_enable` | Enable voice command start/stop control | `true` |

> **Important:** `tracking_radius` must be large enough to cover the guide's lateral movement
> between frames. Values that are too small (e.g. `0.2`) cause the tracker to lose the target
> during turns, making the follower go straight instead of turning.
>
> **Gazebo simulation note:** The RealSense launch files (`rs_gesture.launch.py`,
> `rs_gesture_audio.launch.py`) override three parameters for the simulated depth camera:
> `optical_frame: False` (Gazebo publishes in body frame, not optical frame),
> `min_dist: 0.3` (guide robot front surface appears at ~0.44 m, below the YAML default 0.5),
> and `init_tgt_loc: 0.5` (matching the actual cluster centroid distance). These overrides are
> not needed on real hardware with an Intel RealSense camera.

---

## Guide Robot

The guide robot (airport-style follow-me car) uses a black-and-yellow checkerboard visual
pattern and follows a pre-programmed S-curve trajectory lasting ~50 seconds. It starts facing
the `+X` direction (yaw = 0) so it is immediately visible in the TurtleBot3's sensor FOV.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| TurtleBot3 goes straight, no turning | `tracking_radius` too small | Set `tracking_radius: 1.0` in YAML |
| TurtleBot3 does not move at all | Guide robot facing away | Verify `spawn_gbot.launch.py` uses `-Y 0.0` |
| Target lost immediately (RS) | `z_filter` too high | Set `z_filter: -0.15` in `adbscan_sub_RS.yaml` |
| Gesture node not starting | Python venv not active | Run `source ~/followme_env/bin/activate` first |
| Audio commands not reaching ADBSCAN | Speech node overloaded | Ensure `speech_recognition_pkg` is rebuilt; the node skips empty filenames and holds valid commands for 3 s |
| TTS node fails to start | Missing audio packages | Install audio requirements: `pip3 install librosa openvino simpleaudio sounddevice tqdm inflect` |
| Gazebo fails to start | Stale `gz` process | Run `sudo killall -9 gz ruby` before launching |
