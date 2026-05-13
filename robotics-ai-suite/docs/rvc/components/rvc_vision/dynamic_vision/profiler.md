(profiler)=

# RVC Profiler

The RVC Profiler is an optional component used to profile and benchmark some critical information about RVC

Currently implemented metrics are:

- RGB Image FPS from Intel® RealSense™ [camera node](realsense_node.md)
- Pointcloud data from Intel® RealSense™ [camera node](realsense_node.md)
- Number of inferences per second from [RVC Object Detection](object_detection.md)
- Number of pointcloud alignment from [RVC Pose Detector](pose_detector.md)
- Number of successfully performed Inverse Kinematics from RVC Motion Controller
- Number of failed dead lines from Linux RT kernel scheduler

In this initial release of RVC the metrics are just printed on console every second.
