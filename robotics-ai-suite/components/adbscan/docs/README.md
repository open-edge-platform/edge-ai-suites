---
title: ADBSCAN Algorithm
---

ADBSCAN (Adaptive DBSCAN) is an Intel® patented algorithm. It is a
highly adaptive and scalable object detection and localization
(clustering) algorithm, tested successfully to detect objects at all
ranges for 2D Lidar, 3D Lidar, and Intel® RealSense™ depth camera. This
method automatically computes clustering parameters (radius and minimum
number of points that define a cluster) based on the distance from the
sensor and the data density in its field of view, thus alleviating the
guesswork from parameter selection and enabling efficient hierarchical
clustering. ADBSCAN increases detection range by 30%-40% and detects
20%-30% more objects, compared to the state-of-the-art methods. It has
been gainfully used in multiple applications such as 2D/3D Lidar or
Intel® RealSense™ based object tracking, multi-modal object
classification (Camera + Lidar), surface segmentation, Lidar-based
object classification, occupancy grid generation etc.

## Source Code

The source code of this component can be found here:
[ADBScan](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/adbscan)

## ADBSCAN Tutorials

- [ADBSCAN AAEON Robot](adbscan_aaeon_robot.md)
- [ADBSCAN RealSense](adbscan-realsense.md)
- [ADBSCAN RPLidar](adbscan-rplidar.md)

## ADBSCAN Optimization

- [IA Optimized ADBSCAN Algorithm](IA-optimized-adbscan-algorithm.md)

## Troubleshooting

- Failed to install Deb package: Please make sure to run
  `sudo apt update` before installing the necessary Deb packages.
- You can stop the demo anytime by pressing `ctrl-C`.
