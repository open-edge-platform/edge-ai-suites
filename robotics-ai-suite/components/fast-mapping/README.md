# FastMapping

A ROS project to construct and maintain a volumetric map from a moving RGB-D camera, like [octomap_mapping](https://github.com/OctoMap/octomap_mapping) but runs much faster.

## Component Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/run-fastmapping-algorithm.html)

## Verified Operating Systems

- Ubuntu 22.04 LTS

## Verified ROS Version

- ROS2 Humble - (debian based)

## Dependencies

- [ROS2 Version](https://docs.ros.org/)

## Debian Package Installation

### 1. [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)

### 2. Install the FastMapping debian package

```bash
sudo apt update
sudo apt install ros-humble-fast-mapping
```

### 3. Source the ROS environment

```bash
source /opt/ros/humble/setup.bash
```

### 4. Run the FastMapping sample tutorial using ROSbags

```bash
ros2 launch fast_mapping fast_mapping.launch.py
```

### 5. Run the FastMapping application using Realsense camera input

```bash
ros2 launch fast_mapping fast_mapping_rtabmap.launch.py
```

## Usage

### 1. With depth camera and other SLAM module or fixed tf

As long as there is a SLAM module publishing tf properly (they should), we can get camera poses from the tf tree without any ambiguity of coordinates. The param `external_pose_topic` should be set to 'tf':

```bash
ros2 run fast_mapping fast_mapping_node
```

In this way, the fast_mapping_node will request a transform from the tf tree. This transform is from the map frame, defined by the `map_frame` parameter (the default being "map"), to the optical frame of the camera. This optical frame is specified in the header of the depth image messages (for instance, `camera_color_optical_frame` if you are utilizing a RealSense camera with `rs_aligned_depth.launch`). The transforms that are published to the tf tree do not necessarily need to be in sync with the depth images. ROS tf will carry out a linear interpolation between the nearest available transforms when a transform is requested at a particular time.

The FastMapping algorithm will start and poll until a `CameraInfo` message will come.

```bash
ros2 run fast_mapping fast_mapping_node
[INFO] []: waiting for camera depth info from camera/aligned_depth_to_color/camera_info
[INFO] []: waiting for camera depth info from camera/aligned_depth_to_color/camera_info
[INFO] []: waiting for camera depth info from camera/aligned_depth_to_color/camera_info
```

In parallel start the rosbag file.

```bash
ros2 bag play -s rosbag_v2 <my_ROS1_bagfile.bag>
```

Start rviz2 for visualization.

```bash
rviz2
```

## Running the units tests

For running the unit tests one must navigate to the `build/fast_mapping` directory and execute `make test`.

### 1. Run FastMapping with Intel RealSense cameras

  FastMapping supports mapping from single or multiple Intel RealSense cameras, given that each camera provides a camera_frame <-> map transformation
  in the TF tree, e.g. camera1_color_optical_frame <-> map. FastMapping will only support cameras of the same type and will assume all the
  cameras to have the same set of intrinsics.

  In its default configuration, FastMapping will start mapping from a single camera. In order to run with multiple cameras the parameter 'depth_cameras' must be set
  to the number of required cameras. In addition to the number of cameras, FastMapping expects each depth topic of each camera to be specified
  as well as a topic providing the CameraInfo (intrinsics) as shown in the examples below.

```bash
   source /opt/ros/humble/setup.bash
   ros2 launch fast_mapping fast_mapping_rtabmap.launch.py
```

FastMapping running with two Realsense cameras named "camera_front" and "camera_left"

```bash
   ros2 run fast_mapping fast_mapping_node --ros-args -p depth_cameras:=2 -p depth_topic_1:=camera_front/aligned_depth_to_color/image_raw -p depth_topic_2:=camera_left/aligned_depth_to_color/image_raw -p depth_info_topic:=camera_front/aligned_depth_to_color/camera_info
```

### 2. Run FastMapping with ROS2 bag file

> Make sure to have a ros2 bag file for this test

```bash
   source /opt/ros/humble/setup.bash
   ros2 launch fast_mapping fast_mapping.launch.py 
```
