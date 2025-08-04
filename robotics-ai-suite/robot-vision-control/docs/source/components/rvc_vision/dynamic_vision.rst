
.. _dynamic_vision:

Dynamic Vision
--------------


High performance 2D to 3D object classification and dynamic real-time
space localization

Vision sub components:
^^^^^^^^^^^^^^^^^^^^^^

The Vision container is a special process containing all the vision node in the same process, running
on different threads, to allow zero copy memory operation on large data: RGB and Pointcloud streams.

The component of this container are:


-  :ref:`Realsense Camera node <realsense_node>`
-  :ref:`2D AI perception<object_detection>`. Yolo inference on |OpenVino| provided as example
-  :ref:`3D pointcloud alignment of the object in space<pose_detector>`
-  :ref:`Profiler for performance evaluation<profiler>`

.. _vision_container_high_level_diagram:

.. image:: /images/html/RVCVisionHighLevel.png
    :alt: Vision container high level diagram


The above :ref:`high level diagram <vision_container_high_level_diagram>` shows how the vision
components interact each other:

- The |realsense| node capture and publish RGB and PointCloud streams from the physical camera
- Object Detection node will run AI inference on RGB stream and publish result for Pose Detector
- Pose detector subscribe PointCloud stream and Object detection to align a storage mesh of corresponding class in the subscribed bounding box to the |realsense| PointCloud stream and publish the results in :ref:`RVC Messages <rvc_api_messages>` API format.

.. toctree::
   :maxdepth: 1
   :hidden:

   dynamic_vision/realsense_node
   dynamic_vision/object_detection
   dynamic_vision/pose_detector
   dynamic_vision/profiler

