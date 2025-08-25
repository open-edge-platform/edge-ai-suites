# Efficient Groundfloor Segmentation for 3D Pointclouds

This repository contains a realization of an efficient groundfloor segmentation approach for 3D pointclouds.
The application comes with three default use cases, detailed below.

## Component Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/pointcloud-groundfloor-segmentation.html)

## Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)

## Build process

To build the application please use the following instructions. It requires a ROS2 humble installation as basis and is designed for Ubuntu 22.04 as operating system.

```bash
$> apt install -y $(cat deb_requirements_humble.txt)
$> source /opt/ros/humble/setup.bash
$> colcon build

```

To run the application afterwards, you need to load the application's environment:

```bash
$> source install/setup.bash
```

### Unit tests

Unit tests can be run as follows after building with testing enabled

```bash
$> apt install -y $(cat deb_requirements_humble.txt)
$> source /opt/ros/humble/setup.bash
$> colcon build --cmake-args -DBUILD_TEST=ON
$> source install/setup.bash
$> cd build/pointcloud_groundfloor_segmentation/test
$> ./pointcloud-groundfloor-segmentation-tests
```

## Application use cases

The application is designed as ROS2 node and will provide two output topics:

- /segmentation/labeled_points: A labeled pointcloud, where every point is assigned a classification label, e.g. groundfloor, obstacle, etc.
![Labeled Pointcloud](docs/image1.png)

- /segmentation/obstacle_points: A filtered pointcloud that contains only obstacle points.
![Obstacle Pointcloud](docs/image2.png)

The node operates on a parameter file, that can be provided as launch argument (node_params_file).

### Standalone use with RealSense camera (or other depth cameras)

This use case is intended if the depth output of a RealSense camera should be segmented and converted into a 3D point cloud.

The ROS2 node expects input from a RealSense camera via two topics:

- /<camera_name>/depth/image_rect_raw
- /<camera_name>/depth/camera_info

where <camera_name> is a commandline parameter for the launch command. By default <camera_name> is 'camera'

```bash
$> source /opt/ros/humble/setup.bash
$> source install/setup.bash
$> ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py
```

### Use together with Wandering demo on Aaeon robot

This use case is intended for the wandering application running on the Aaeon robot. It basically uses the same functionality as the default wandering application, but uses the RealSense depth stream instead of a 2D laser scan to create the global and local costmap for navigation.

```bash
$> /opt/ros/humble/share/pointcloud_groundfloor_segmentation/scripts/wandering_aaeon.sh
```

An example of a local costmap based on the RealSense depth input is provided in the image above.

### Use with 3D pointcloud

Finally, this application can also be used directly with a 3D pointcloud as input.

```bash
$> source /opt/ros/humble/setup.bash
$> source install/setup.bash
$> ros2 launch pointcloud_groundfloor_segmentation pointcloud_groundfloor_segmentation_launch.py
```

The input topic name can be provided using the commandline parameter 'pointcloud_topic'.
