.. adbscan-algorithm:

ADBSCAN Algorithm
==================

ADBSCAN (Adaptive DBSCAN) is an |intel| patented algorithm. It is a highly adaptive and scalable object detection and localization (clustering) algorithm, tested successfully to detect objects at all ranges for 2D Lidar, 3D Lidar, and |realsense| depth camera.
This method automatically computes clustering parameters (radius and minimum number of points that define a cluster) based on the distance from the sensor and the data density in its field of view, thus alleviating the guesswork from parameter selection and enabling efficient hierarchical clustering.
ADBSCAN increases detection range by 30%-40% and detects 20%-30% more objects, compared to the state-of-the-art methods. It has been gainfully used in multiple applications such as 2D/3D Lidar or |realsense| based object tracking, multi-modal object classification (Camera + Lidar), surface segmentation, Lidar-based object classification, occupancy grid generation etc. 


Source Code
-----------

The source code of this component can be found here: `ADBScan <https://github.com/open-edge-platform/edge-ai-suites/robotics-ai-suite/components/adbscan>`_


ADBSCAN Tutorials
-----------------

.. toctree::
   :maxdepth: 1

   adbscan-rplidar
   adbscan-realsense
   adbscan_aaeon_robot


ADBSCAN Optimization
--------------------

.. toctree::
   :maxdepth: 1

   IA-optimized-adbscan-algorithm


Troubleshooting
----------------------------

- Failed to install |deb_pack|: Please make sure to run ``sudo apt update`` before installing the necessary |deb_packs|.

- You can stop the demo anytime by pressing ``ctrl-C``.

- For general robot issues, go to: :doc:`../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.

