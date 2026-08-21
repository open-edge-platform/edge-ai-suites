# ADBSCAN Follow-me

ADBSCAN (Adaptive DBSCAN) is an Intel® algorithm for adaptive object detection
and localization from 2D LiDAR, 3D LiDAR, and RealSense depth-camera
point clouds. It automatically determines clustering parameters from sensor
range and point density, reducing manual tuning for perception workloads.

The Follow-me application uses ADBSCAN to locate a target person and publish
robot velocity commands. This guide combines the supported optimization workflow
with one Gazebo simulation and one Clearpath Jackal deployment scenario.

## Source Code

[ADBScan source code](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/adbscan)

## Intel-Optimized ADBSCAN

```{include} includes/adbscan-optimization.md
:start-line: 2
```

## Simulate Follow-me in Gazebo

```{include} includes/follow-me-simulation.md
:start-line: 2
```

## Deploy Follow-me on a Clearpath Jackal

```{include} includes/follow-me-deployment.md
:start-line: 2
```