(dynamic_vision)=

# Dynamic Vision

High performance 2D to 3D object classification and dynamic real-time
space localization

## Vision sub components:

The Vision container is a special process containing all the vision node in the same process, running
on different threads, to allow zero copy memory operation on large data: RGB and Pointcloud streams.

The component of this container are:

- [Realsense Camera node](dynamic_vision/realsense_node.md)
- [2D AI perception](dynamic_vision/object_detection.md). Yolo inference on OpenVINO™ provided as example
- [3D pointcloud alignment of the object in space](dynamic_vision/pose_detector.md)
- [Profiler for performance evaluation](dynamic_vision/profiler.md)

![Vision container high level diagram](images/html/RVCVisionHighLevel.png)

The above diagram shows how the vision
components interact with each other:

- The Intel® RealSense™ camera node captures and publishes RGB and Point Cloud streams from the physical camera.

- The Object Detection node runs AI inference on the RGB stream and publishes the result for the Pose Detector.

- The Pose Detector subscribes to the Point Cloud stream and aligns the 3D data from the stream, with the storage mesh of corresponding classes in the subscribed bounding box. The Pose Detector then publishes the results in the [RVC Messages'](../rvc_api.md) API format.

<!--hide_directive
:::{toctree}
:maxdepth: 1
:hidden:

dynamic_vision/realsense_node
dynamic_vision/object_detection
dynamic_vision/pose_detector
dynamic_vision/profiler

:::
hide_directive-->
