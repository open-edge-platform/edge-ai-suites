
.. _profiler:

RVC Profiler
^^^^^^^^^^^^^^^^

The RVC Profiler is an optional component used to profile and benchmark some critical information about RVC

Currently implemented metrics are:

- RGB Image FPS from |realsense| :ref:`camera node<realsense_node>`
- Pointcloud data from |realsense|  :ref:`camera node<realsense_node>`
- Number of inferences per second from :ref:`RVC Object Detection<object_detection>`
- Number of pointcloud alignment from :ref:`RVC Pose Detector<pose_detector>`
- Number of successfully performed Inverse Kinematics from RVC Motion Controller
- Number of failed dead lines from |Linux| RT kernel scheduler


In this initial release of |RVC| the metrics are just printed on console every second.
