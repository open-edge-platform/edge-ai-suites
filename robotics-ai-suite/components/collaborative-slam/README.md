# Collaborative SLAM

## Component Documentation

Comprehensive documentation on this component is available here: [Link](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/collaborative-slam.html)

## Overview

This is a collaborative SLAM system. The main input should come from a camera, either monocular, or stereo, or RGB-D. It also supports wheel odometry, IMU and 2D LiDAR data as auxiliary input. The output include the estimated pose of the camera and visualization of the internal map. All inputs and outputs are in standard ROS formats.

There are four components:
- The tracker is a visual SLAM system with support for odometry, inertial and 2D LiDAR input. It estimates the camera pose in real-time, and maintains a local map. It can work as a standalone node. But if the server is online, it will communicate with the server to query and update the map.
- The server maintains the maps and communicates with all trackers. For each new keyframe from a tracker, it detects possible loops, both intra-map and inter-map. Once detected, the server will perform map optimization or map merging, and distribute the updated map to corresponding trackers.
- The msgs package defines the message between server and tracker.
- The slam package that contains the code of the SLAM algorithm.

Refer to [this paper](https://arxiv.org/abs/2102.03228) for more explanation of the system.

### System Requirement

We support Ubuntu 22.04 with [ROS 2 Humble](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html).

### Third-party Dependencies

We depend on Eigen, OpenCV and yaml-cpp. They should have already been in your system if you have the full ROS installation. If not, try with `sudo apt install libeigen3-dev libopencv-dev libyaml-cpp-dev libsuitesparse-dev`.

We also depend on [DBoW2](https://github.com/shinsumicco/DBoW2), [g2o](https://github.com/RainerKuemmerle/g2o), [nlohmann/json](https://github.com/nlohmann/json) and [spdlog](https://github.com/gabime/spdlog). They are included in this repo as git submodule, so that you do NOT have to download or install them manually.

### Clone and Build

To setup, clone or download UnivLoc into a colcon workspace, and build with `colcon build`:

```bash
git clone --recursive https://github.com/open-edge-platform/edge-ai-suites
# If you have cloned the repo without the --recursive flag, run the following command to remedy:
#git submodule update --init --recursive

cp -r edge-ai-suites/robotics-ai-suite/components/collaborative-slam YOUR_COLCON_WORKSPACE/src
cd YOUR_COLCON_WORKSPACE/src

cd ..
# build with native support (default build - some platforms not supported)
colcon build

# build without native support
colcon build --cmake-args -DBUILD_NATIVE=OFF
# or without tests
colcon build --cmake-args -DBUILD_TESTING=OFF -DBUILD_NATIVE=OFF
# build with tremont architecture support (some platforms not supported)
colcon build --cmake-args -DBUILD_TREMONT=ON

Note: If not defined, default values will be BUILD_NATIVE=ON, BUILD_TREMONT=OFF

# build in debug mode
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Debug

Note: for cases when BUILD_NATIVE=OFF or using debug mode, the g2o optimization might not work properly, which can lead to degraded performance.
```

To leverage GPU, check this [guide](docs/GPU_CM.md) for environment setup.

### Run

The tracker and server are ROS programs. All the configurations are passed with ROS parameters. Check [tracker.launch.py](tracker/launch/tracker.launch.py)
and [server.launch.py](server/launch/server.launch.py) for all available parameters and comments.
For ROS2, parameters and launch file are separated and parameters are stored in [tracker.yaml](tracker/config/tracker.yaml).  
There are ready-to-use configurations for RealSense D400-Series RGBD camera or the OpenLORIS-Scene dataset (`tracker.launch.py`), the TUM RGBD dataset (`tum_rgbd.launch.py`), the EuRoC dataset (`euroc_mono.launch.py` or `euroc_stereo.launch.py`), the KITTI dataset (`kitti_mono.launch.py` or `kitti_stereo.launch.py`).

Collaborative SLAM currently supports total 4 operating modes, including mapping, localization, remapping and relocalization modes. We provide `slam_mode` option for the tracker and `server_mode` option for the server to configure.
The default values of these two options are "mapping" and a mismatch of the tracker and server modes may lead to unpredictable result. Currently, the relocalization mode is more for a developer or debugging use-case.

**To support multi-robot or multi-camera or loop closure or map saving, launch univloc_server first; otherwise, only launching univloc_tracker is enough.**
```bash
# For stereo/rgbd/visual-inertial cases
ros2 launch univloc_server server.launch.py

# For monocular case
ros2 launch univloc_server server.launch.py fix_scale:=false
```
On each robot run the tracker node with unique ID:
```bash
# remember to replace <if_specific> and <unique_id> with your own setup
ros2 launch univloc_tracker tracker.launch.py camera:=<if_specific> publish_tf:=false queue_size:=0 ID:=<unique_id> rviz:=false gui:=false camera_fps:=30.0
```

If the server is on another machine, choose a domain ID between 0 and 101 (inclusive) and set `ROS_DOMAIN_ID` for both machines; remember to source environment setup file afterwards. See [ros2 offical doc](https://docs.ros.org/en/humble/Concepts/About-Domain-ID.html) for a reference.
The server will publish map elements on the topics of /univloc_server/{keypoints,keyframes}, which can be visualized in RViz.

**ROS 2 example with a RealSense D400-Series camera**

```bash
# Terminal A - run the server
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_server server.launch.py fix_scale:=<mono:false rgbd:true>

# Terminal B - run the tracker for RGBD case
# Please change the value of camera_fps that represents the real FPS of input camera images, the default value is 30.0 if you don't specify it
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_tracker tracker.launch.py camera:=camera get_camera_extrin_from_tf:=false pub_tf_child_frame:=camera_link camera_fps:=30.0

# Terminal B - or run the tracker for monocular case
ros2 launch univloc_tracker tracker.launch.py camera_setup:=Monocular camera:=camera get_camera_extrin_from_tf:=false pub_tf_child_frame:=camera_link camera_fps:=30.0

# Terminal C - start realsense camera
ros2 launch realsense2_camera rs_launch.py align_depth:=true align_depth.enable:=true init_reset:=true
```

**ROS 2 example with the market1-1 data sequence from the OpenLORIS-Scene dataset**

Collaborative SLAM supports the [OpenLORIS-Scene Dataset](https://lifelong-robotic-vision.github.io/dataset/scene.html). The ROS bag files for the sequences can be downloaded after filling the form. In order to run the OpenLORIS-Scene dataset in RGBD or monocular case, do the following:

```bash
# Terminal A - run the server
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_server server.launch.py fix_scale:=<mono:false rgbd:true>

# Terminal B - run the tracker for RGBD case
source YOUR_COLCON_WS/install/setup.bash
# define an unlimited queue size to make sure every frame is processed
ros2 launch univloc_tracker tracker.launch.py camera:=d400 publish_tf:=false queue_size:=0 camera_fps:=30.0

# Terminal B - or run the tracker for monocular case
ros2 launch univloc_tracker tracker.launch.py camera_setup:=Monocular camera:=d400 publish_tf:=false queue_size:=0 camera_fps:=30.0

# Terminal C - run the ROS bag file
sudo apt install ros-humble-rosbag2-bag-v2-plugins libroscpp-dev libroslz4-dev  # install rosbag2_bag_v2 and dependency if you don't have
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
ros2 bag play -s rosbag_v2 OPENLORIS/market1-1.bag
```

**ROS 2 example with the rgbd_dataset_freiburg1_floor data sequence from the TUM RGB-D dataset**

Collaborative SLAM supports the [TUM RGB-D Dataset](https://vision.in.tum.de/data/datasets/rgbd-dataset/download). The ROS bag files for the sequences can be downloaded in the detailed description of sequences. Note that the downloaded ROS bag files are compressed,
it can be decompressed using command like ```rosbag decompress xxx.bag```. In order to run the TUM RGB-D dataset in RGBD or monocular case, do the following:

```bash
# Terminal A - run the server
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_server server.launch.py fix_scale:=<mono:false rgbd:true>

# Terminal B - run the tracker for RGBD case
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_tracker tum_rgbd.launch.py gui:=false rviz:=false publish_tf:=false log_level:=warning fr<sequence_number>:=true

# Terminal B - or run the tracker for monocular case
ros2 launch univloc_tracker tum_rgbd.launch.py camera_setup:=Monocular gui:=false rviz:=false publish_tf:=false log_level:=warning fr<sequence_number>:=true

# Terminal C - run the ROS bag file
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
ros2 bag play -s rosbag_v2 TUM/rgbd_dataset_freiburg1_floor.bag
```

Supported sequence group: `fr1`, `fr2`, `fr3`.

**ROS 2 example with the V2_01_easy data sequence from the EuRoC dataset**

Collaborative SLAM supports the [EuRoC MAV Dataset](https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets). The ROS bag files for the sequences can be downloaded in the "ROS bag" section. In order to run the EuRoC dataset in stereo(+imu) or monocular(+imu) case, do the following:

```bash
# Terminal A - run the server
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_server server.launch.py fix_scale:=<mono:false stereo/mono-imu/stereo-imu:true> correct_loop:=true

# Terminal B - run the tracker for stereo case
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_tracker euroc_stereo.launch.py camera_setup:=Stereo gui:=false rviz:=false publish_tf:=false log_level:=warning

# Terminal B - or run the tracker for monocular case
ros2 launch univloc_tracker euroc_mono.launch.py gui:=false rviz:=false publish_tf:=false log_level:=warning

# Terminal B - or run the tracker for stereo+imu case
ros2 launch univloc_tracker euroc_stereo.launch.py camera_setup:=Stereo_Inertial gui:=false rviz:=false publish_tf:=false log_level:=warning clean_keyframe:=true

# Terminal B - or run the tracker for monocular+imu case
ros2 launch univloc_tracker euroc_mono.launch.py camera_setup:=Monocular_Inertial gui:=false rviz:=false publish_tf:=false log_level:=warning clean_keyframe:=true

# Terminal C - run the ROS bag file
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
ros2 bag play -s rosbag_v2 EuRoC/V2_01_easy.bag
```

**ROS 2 example with the KITTI odometry grayscale sequences**

Collaborative SLAM supports the [KITTI odometry grayscale dataset](http://www.cvlibs.net/datasets/kitti/eval_odometry.php).
In order to run the KITTI dataset in stereo or monocular case, do the following:

```bash
# Terminal A - run the server
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_server server.launch.py fix_scale:=<mono:false stereo:true>

# Terminal B - run the tracker for stereo case
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_tracker kitti_stereo.launch.py camera_setup:=Stereo gui:=false rviz:=false publish_tf:=false log_level:=warning s<sequence_number>:=true

# Terminal B - or run the tracker for monocular case
ros2 launch univloc_tracker kitti_mono.launch.py gui:=false rviz:=false publish_tf:=false log_level:=warning s<sequence_number>:=true

# Terminal C - run the ROS bag file
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
ros2 bag play -s rosbag_v2 kitti_data_odometry_gray_sequence_<sequence_number>.bag
```

Supported sequence group: `s00_02`, `s03`, `s04_12`.

**ROS 2 example with namespace**
```bash
source YOUR_COLCON_WS/install/setup.bash
ros2 launch univloc_tracker tracker.launch.py camera:=d400 publish_tf:=false queue_size:=0 ID:=0 namespace:=robot1 camera_fps:=30.0

# In another terminal:
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
# remap the topics subscribed to by the tracker, to be listed under the specified namespace i.e robot1
ros2 bag play -s rosbag_v2 market1-1-multi.bag --remap /d400/aligned_depth_to_color/image_raw:=/robot1/d400/aligned_depth_to_color/image_raw /d400/color/camera_info:=/robot1/d400/color/camera_info /d400/color/image_raw:=/robot1/d400/color/image_raw
```


**To enable/disable resetting the system if consecutively lost for a specified number of frames.**
```bash
# Disable resetting (default option)
ros2 launch univloc_tracker tracker.launch.py camera_fps:=30.0
# Enable resetting if consecutively lost for 10 frames
ros2 launch univloc_tracker tracker.launch.py camera_fps:=30.0 num_lost_frames_to_reset:=10
```

- Disabling resetting the system is the same strategy adopted in OpenVSLAM and it will try to relocalize using the local map after lost, which avoids the generation of multiple trajectory output files.

- Enabling resetting the system is useful for large-scale scenarios where the robot constantly explores new environments and it is difficult to relocalize using the local map.

**Relocalization mode**

Collaborative SLAM, besides mapping, localization and remapping, has a relocalization mode which is used only for
debugging. The map already needs to be created and one can use relocalization mode for a short
sequence to verify if a robot can be relocalized in a specific place on the map. Relocalization mode does
not support publishing tf. Therefore `publish_tf` parameter needs to be set to `false`.
Command example can be found below (command used after the area has been mapped):
```bash
#Server
ros2 launch univloc_server server.launch.py server_mode:=relocalization fix_scale:=true load_map_path:=/path/to/saved/map/map.msg

#Tracker
ros2 launch univloc_tracker tracker.launch.py publish_tf:=false queue_size:=0 rviz:=false gui:=true slam_mode:=relocalization traj_store_path:=/path/to/saved/map/ map_frame:=map-0 camera_fps:=30.0
```

**Enabling Fast Mapping support**

Collaborative SLAM can generate both a 3D Volumetric Map and a 2D Occupancy Grid (used for navigation) by enabling
Fast Mapping support. By default, Fast Mapping support is disabled, but setting `enable_fast_mapping` parameter to `true`
will enable Fast Mapping that will result in the topics `map`(2D) and `fused_map`(3D) maps being published.
The parameters for configuring Fast Mapping are present in the [tracker.yaml](tracker/config/tracker.yaml).

### Documentation

Documentations are placed under docs folder.

For enabling imu and odometry data, you can refer to [use_odometry.md](docs/use_odometry.md), [use_imu.md](docs/use_imu.md).

For localization mode, saving map or trajectory for evaluation, you can refer to [geekplus_doc.md](docs/geekplus_doc.md).

For remapping mode, updating pre-constructed keyframe/landmark map and octree map with manual region input from user, you can refer to [remapping_mode.md](docs/remapping_mode.md).
