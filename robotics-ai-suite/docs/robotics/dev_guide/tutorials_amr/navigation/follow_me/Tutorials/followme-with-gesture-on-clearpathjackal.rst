.. followme-with-gesture on jackal robot:

Follow-me with ADBSCAN and Gesture-based Control on |clearpath_robotics| |jackal| Robot
=========================================================================================

This tutorial demonstrates the Follow-me algorithm along with a gesture recognition network, where the robot follows a target person in real time and responds to state commands through hand gestures. 
This tutorial uses |clearpath_robotics| |jackal| robot and one |realsense| D400 series camera.
This camera provides the point cloud data as input for the |intel|-patented object detection algorithm Adaptive DBSCAN to detect the position of the target person. This camera also provides RGB images to the object detection network responsible for detecting hand gestures for controlling the robot's start and stop states.
This RGB image is passed through a deep learning-based gesture recognition pipeline, called `Mediapipe Hands Framework <https://mediapipe.readthedocs.io/en/latest/solutions/hands.html>`__, to detect the gesture category. 
The motion commands for the robot are published to ``twist`` topic based on these two outputs: person's position and gesture category. 

To start, the robot requires two conditions at the same time:

- The target person will be within the tracking radius (a reconfigurable parameter in the parameter file in ``/opt/ros/humble/share/tutorial-follow-me-w-gesture/params/followme_adbscan_RS_params.yaml``) of the robot.

-  The detected gesture of the target is ``thumbs up``.

Once the starting criteria are met, the robot keeps following the target unless one of the below stopping conditions are triggered:

-  The target moves to a distance greater than the tracking radius (a reconfigurable parameter in the parameter file in ``/opt/ros/humble/share/tutorial-follow-me-w-gesture/params/followme_adbscan_RS_params.yaml``).

-  The detected gesture is ``thumbs down``.

Getting Started
----------------


Install the |deb_pack|
^^^^^^^^^^^^^^^^^^^^^^^

Install ``ros-humble-follow-me-tutorial-w-gesture`` |deb_pack| from |lp_amr| APT repository.

.. code-block:: bash

   sudo apt update
   sudo apt install ros-humble-follow-me-tutorial-w-gesture

Install Python Modules
^^^^^^^^^^^^^^^^^^^^^^^

This application uses `Mediapipe Hands Framework <https://mediapipe.readthedocs.io/en/latest/solutions/hands.html>`__
for hand gesture recognition. Install the following modules as a prerequisite for the framework:
   
.. code-block:: bash

   pip3 install mediapipe
   pip3 install numpy==1.24.3

.. _followme-gesture-realsense-on-clearpathjackal:

Identify serial number of Realsense Camera
-------------------------------------------

Install the |realsense| utilities package to easily read the correct serial number:
    
.. code-block:: bash

   sudo apt install librealsense2-utils

Check the Serial number:

.. code-block:: console

   $rs-enumerate-devices | grep Serial
    Serial Number                 :     108322074411
    Asic Serial Number            :     108223052439


You will use this serial number (and not the ASIC Serial Number) when launching the demo below.
         

Run Demo with |realsense| Camera
---------------------------------

Execute the following script to launch Follow-Me with Gesture on the |clearpath_robotics| |jackal| robot:

.. code-block:: bash

   source /opt/ros/humble/setup.bash
   /opt/ros/humble/share/tutorial-follow-me-w-gesture/scripts/jackal-follow-me-w-gesture.sh <Camera Serial Number>


<Camera Serial Number>: Use the serial number returned when using `rs-enumerate-devices`. Note that the output of other programs like `lsusb` might return an incorrect serial number.
 
After starting the script, the robot should begin searching for trackable objects in its initial detection radius (defaulting to around 0.5m), and then following acquired targets as soon as they provide a ``thumbs up`` to the |realsense| camera and move from the initial target location.

.. note::

   There are reconfigurable parameters in ``/opt/ros/humble/share/tutorial-follow-me-w-gesture/params`` directory for the |realsense| camera (`followme_adbscan_RS_params.yaml`). You can modify parameters depending on the respective robot, sensor configuration and environments (if required) before running the tutorial.
   Find a brief description of the parameters in the following table:

   .. list-table:: Configurable Parameters
      :widths: 20 80

      * - ``Lidar_type``
        - Type of the point cloud sensor. For |realsense| camera and LIDAR inputs, the default value is set to ``RS`` and ``2D``, respectively.
      * - ``Lidar_topic``
        - Name of the topic publishing point cloud data.
      * - ``Verbose``
        - If this flag is set to ``True``, the locations of the detected target objects will be printed as the screen log.
      * - ``subsample_ratio``
        - This is the downsampling rate of the original point cloud data. Default value = 15 (i.e. every 15-th data in the original point cloud is sampled and passed to the core ADBSCAN algorithm).
      * - ``x_filter_back``
        - Point cloud data with x-coordinate > ``x_filter_back`` are filtered out (positive x direction lies in front of the robot).
      * - ``y_filter_left``, ``y_filter_right``
        - Point cloud data with y-coordinate > ``y_filter_left`` and y-coordinate < ``y_filter_right`` are filtered out (positive y-direction is to the left of robot and vice versa).
      * - ``z_filter``
        - Point cloud data with z-coordinate < ``z_filter`` will be filtered out. This option will be ignored in case of 2D Lidar.
      * - ``Z_based_ground_removal``
        - Filtering in the z-direction will be applied only if this value is non-zero. This option will be ignored in case of 2D Lidar.
      * - ``base``, ``coeff_1``, ``coeff_2``, ``scale_factor``
        - These are the coefficients used to calculate adaptive parameters of the ADBSCAN algorithm. These values are pre-computed and recommended to keep unchanged.
      * - ``init_tgt_loc``
        - This value describes the initial target location. The person needs to be at a distance of ``init_tgt_loc`` in front of the robot to initiate the motor.
      * - ``max_dist``
        - This is the maximum distance that the robot can follow. If the person moves at a distance > ``max_dist``, the robot will stop following.
      * - ``min_dist``
        - This value describes the safe distance the robot will always maintain with the target person. If the person moves closer than ``min_dist``, the robot stops following.
      * - ``max_linear``
        - Maximum linear velocity of the robot.
      * - ``max_angular``
        - Maximum angular velocity of the robot.
      * - ``max_frame_blocked``
        - The robot will keep following the target for ``max_frame_blocked`` number of frames in the event of a temporary occlusion.
      * - ``tracking_radius``
        - The robot will keep following the target as long as the current target location = previous location +/- ``tracking_radius``

Troubleshooting
----------------------------

- Failed to run the tutorial mentioning permission denied on ``/dev/dri/render128``

  .. code-block:: bash

     usermod -a -G render $USER

  **Note**: The machine may need to be restarted after adding the user to a new group.

- Failed to install |deb_pack|: Please make sure to run ``sudo apt update`` before installing the necessary |deb_packs|.

- You may stop the demo anytime by pressing ``ctrl-C``.

- If the robot rotates more than intended at each step, try reducing the parameter ``max_angular`` in the parameter file.

- If the motor controller board does not start, restart the robot.

- For general robot issues, go to: :doc:`../../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.

