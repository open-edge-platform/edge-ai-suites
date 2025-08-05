.. |dev_guide| image:: ../images/icons/Developer_Guide.png
   :width: 70
   :align: bottom

Developer Guide |dev_guide|
==========================================


The |lp_amr| provides software packages and pre-validated hardware modules for
sensor data ingestion, classification, environment modeling, action
planning, action control. Built on the (|l_ros|) robot operating system,
it also features reference algorithms and working examples.


Beyond autonomous mobility, this package demonstrates map building
and Simultaneous Localization And Mapping (SLAM) loop closure
functionality. It utilizes an open source version of visual SLAM
with input from an |realsense| camera. Optionally, the
package allows you to run Light Detection and Ranging (LiDAR) based SLAM
and compare those results with visual SLAM results on accuracy and
performance indicators. Additionally, it detects and highlights the objects
on the map. Depending on the platform that is used,
workloads are executed on an integrated GPU or on |intel| CPU.


The |p_amr| addresses
industrial, manufacturing, consumer market, and smart cities use
cases, facilitating data collection, storage, and analytics across
various nodes on the factory floor.

.. toctree::
   :maxdepth: 1

   how_it_works/index
   requirements
   tutorials_amr/index
   system_integrator/index
   terminology
