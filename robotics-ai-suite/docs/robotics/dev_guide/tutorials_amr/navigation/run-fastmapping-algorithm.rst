.. run-fastmapping-algorithm:

FastMapping Algorithm
======================

FastMapping application is the |intel| optimized version of octomap.

For more information on FastMapping, see :ref:`how_it_works`.


Source Code
-----------

The source code of this component can be found here: `FastMapping <https://github.com/open-edge-platform/edge-ai-suites/robotics-ai-suite/components/fast-mapping>`_


Run the FastMapping Standalone Application
--------------------------------------------

#. To download and install the FastMapping standalone sample application run the command below:


   .. code-block::

      sudo apt-get install ros-humble-fast-mapping    

   .. note::

      The ``ros-humble-fast-mapping`` package includes a |ros| bag, which will be used for this tutorial. 
      After the installation, the |ros| bag can be found at ``/opt/ros/humble/share/bagfiles/spinning/``

#. Set up your |ros| environment 

   .. code-block::

      source /opt/ros/humble/setup.bash 

#. Run the FastMapping sample application using a |ros| bag of a robot spinning:

   .. code-block::

      ros2 launch fast_mapping fast_mapping.launch.py


   Expected output:

   .. video:: ../../../videos/fast_mapping.mp4
      :preload: none
      :width: 900

#. Run the FastMapping sample application using |realsense| camera input with RTAB-Map:

   .. code-block::

      ros2 launch fast_mapping fast_mapping_rtabmap.launch.py

Once the tutorial is launched, the input from the |realsense| camera is used and a 3D voxel map of the environment can be viewed in rviz.

To close this application, type ``Ctrl-c`` in the terminal where you ran the launch script.


Troubleshooting
---------------


For general robot issues, go to: :doc:`../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.
