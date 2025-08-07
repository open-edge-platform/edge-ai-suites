# ADBSCAN

## Component Documentation

Comprehensive documentation on this component is available here: [Link](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/adbscan/index.html)

## ADBSCAN algorithm Description
ADBSCAN stands for Adaptive Density-based Spatial Clustering of Applications with Noise.
DBSCAN is an unsupervised clustering algorithm that clusters high dimensional points based on their distribution density.
ADBSCAN is an improvement over the classic DBSCAN algorithm where the clustering parameters are adaptive based on the range, and especially suitable for processing Lidar data. 
It is an Intel-patented algorithm which improves the object detection range by 20-30% on average.

This repository contains several AMR (autonomous Mobile Robot) algorithm implementations based on ADBSCAN. A short description of each of these algorithms is as follows:

### ROS2_node
This is a ROS2 package for ADBSCAN algorithm. It contains a ROS2 node which subscribes to pointcloud sensors (LIDAR/ Realsense camera) and publishes a list of objects in ObstacleArray message format.
Find instructions for this package [here](ROS2_node/Readme.md)

### Standalone
This directory contains standalone C++ source code for the ADBSCAN algorithm. Sample pointcloud input files to run the executable are available [here](./input).

### Visualization
This directory contains necessary python scripts to visualize the bounding box of the object clusters in the pointcloud data.

### Follow_me_RS_2D
This is a ROS2 package for an AMR algorithm where a robot follows a target person. It contains a ROS2 node which subscribes to pointcloud sensors (LIDAR/ Realsense camera),
uses the ADBSCAN algorithm to cluster the data and detect the location of the target person and subsequently, publishes the velocity commands for a differential drive robot. This package contains another version of the follow-me application: gesture-based follow-me. This version integrates a gesture recognition model to the existing implementation to control the movement of robot with hand gestures of the target person.
Find instructions for this package [here](Follow_me_RS_2D/Readme.md)

### package/tutorial_follow_me
This package contains a ROS2 tutorial to run the follow-me application on a custom AAEON robot.

### nav2_dynamic_msgs
This is an associate ROS2 package consisting of custom msgs for obstacle and obstactle arrays. Adbscan and follow-me depend on this package for publishing the obstactle locations. It has been sourced from [this repo](https://github.com/ros-planning/navigation2_dynamic).


All of these ROS2 packages are supported by the following platforms:
- OS: Ubuntu 22.04
- ROS version: ROS2 Humble



