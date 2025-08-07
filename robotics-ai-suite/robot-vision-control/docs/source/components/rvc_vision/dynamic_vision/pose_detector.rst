
.. _pose_detector:

Pose Detector
^^^^^^^^^^^^^^^^

The last stage of the dynamic use cases Vision component of RVC is the Pose Detector.

Its role is to acquire the :ref:`RVC Vision Messages<rvc_vision_messages>` RotateBBList message subscribing from the object detection component
and the `PointCloud2 <https://docs.ros2.org/foxy/api/sensor_msgs/msg/PointCloud2.html>`_ : message from |realsense| camera node

With these information, using the pointcloud representation of the objects from storage, the Pose 
Detector will try to find instances of the idea object in the camera pointcloud scene.

The corresponding mesh in pcd format is used according to the RotatedBB class id, so if the Object Detection
found a cube, the pose detector will use the cube.pcd to try to find the cube in the |realsense| PCL scene.

The package providing the object pcd files is specified in the yaml file as ``rvc_use_case_binaries`` as described below


This node accept following parameters:

-  class_name_array: filenames to load from file, pose detector will append `.pcd` and search in the
   rvc_use_case_binaries package, subdirectory `pcd_objects`
-  rvc_use_case_binaries: package name providing the needed binaries as per previous parameters

The following parameters fine tune the internal pointcloud ransac algorithm aligning the mesh loaded
from storage to the |realsense| point cloud output. 
For further information, refer to `SampleConsensusPrerejective <https://pointclouds.org/documentation/classpcl_1_1_sample_consensus_prerejective.html>`_.
For a sample explanation, refers to `PCL Alignment Prerejective <https://pcl.readthedocs.io/projects/tutorials/en/latest/alignment_prerejective.html>`_

-  downsampling
-  downsample_clouds
-  normal_search_radius
-  fpfh_search_radius
-  stddev_mul_threshold
-  z_threshold
-  inlier_fraction
-  similarity_threshold
-  max_corresp_randomness
-  max_corresp_distance
-  max_iterations
-  num_samples
-  icp_max_corresp_distance
-  icp_xform_epsilon
-  icp_fitness_epsilon
-  icp_max_iterations


Default Config file
""""""""""""""""""""


.. code-block:: yaml

            class_name_array: [ 'bolt', 'gear', 'nut', 'cube' ]
            downsampling: 0.0055
            downsample_clouds: 0.0055
            normal_search_radius: 0.005
            fpfh_search_radius: 0.05
            stddev_mul_threshold: 0.0
            z_threshold: 0.66
            inlier_fraction: 0.47
            similarity_threshold: 0.86
            max_corresp_randomness: 214.0
            max_corresp_distance: 0.1
            max_iterations: 1000
            num_samples: 3
            icp_max_corresp_distance: 0.1
            icp_xform_epsilon: 0.000000001
            icp_fitness_epsilon: 0.000006
            icp_max_iterations: 50
            rvc_use_case_binaries: rvc_use_case_binaries
