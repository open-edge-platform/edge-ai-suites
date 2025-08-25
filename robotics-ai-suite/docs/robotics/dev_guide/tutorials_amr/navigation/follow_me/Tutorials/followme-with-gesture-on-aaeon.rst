.. followme-with-gesture on aaeon robot:

Follow-me with ADBSCAN and Gesture-based Control on Aaeon Robot
=================================================================

This tutorial demonstrates the Follow-me algorithm with gesture, where the robot follows a target person in real time. 
The movement of the robot can be controlled by the person's position (relative to the robot) as well as the hand gestures. 
This tutorial is demonstrated on Aaeon robot using 2 front-mounted |realsense| cameras: camera 1 and camera 2. 
Camera 1 takes the point cloud data as inputs and passes it through |intel|-patented object detection algorithm, namely Adaptive DBSCAN, to detect the position of the target person.
Camera 2 is positioned at a certain height for capturing the RGB images of the target's hand gestures. 
This RGB image is passed through a deep learning-based gesture recognition pipeline, called `Mediapipe Hands Framework <https://mediapipe.readthedocs.io/en/latest/solutions/hands.html>`__, to detect the gesture category. 
The motion commands for the robot are published to ``twist`` topic based on these two outputs: person's position and gesture category. 

The two conditions required to start the robot's movement are as follows:

-  The target person will be within the tracking radius (a reconfigurable parameter in the parameter file in `/opt/ros/humble/share/tutorial-follow-me-w-gesture/params/followme_adbscan_RS_params.yaml`) of the robot.

-  The detected gesture of the target is ``thumbs up``.

Once the starting criteria are met, the robot keeps following the target unless one of the below stopping conditions holds true:

-  The target moves to a distance greater than the tracking radius (a reconfigurable parameter in the parameter file in `/opt/ros/humble/share/tutorial-follow-me-w-gesture/params/followme_adbscan_RS_params.yaml`).

-  The detected gesture is ``thumbs down``.

Getting Started
----------------


Install the |deb_pack|
^^^^^^^^^^^^^^^^^^^^^^^

Install ``ros-humble-follow-me-tutorial-w-gesture`` |deb_pack| from |intel| |p_amr| APT repository.

   .. code-block::

      sudo apt update
      sudo apt install ros-humble-follow-me-tutorial-w-gesture

Install Python Modules
^^^^^^^^^^^^^^^^^^^^^^^

This application uses `Mediapipe Hands Framework <https://mediapipe.readthedocs.io/en/latest/solutions/hands.html>`__
for hand gesture recognition. Install the following modules as a prerequisite for the framework:
   
   .. code-block::

      pip3 install mediapipe
      pip3 install numpy==1.24.3

.. _followme-gesture-realsense-on-aaeon-robot:

Identify serial number of Realsense Camera
-------------------------------------------

Install package
    
   .. code-block::

         sudo apt install librealsense2-utils

Check the Serial number

    .. code-block::

         $rs-enumerate-devices | grep Serial
             Serial Number                 :     108322074411
             Asic Serial Number            :     108223052439


Serial Number is the one which has to be used while launching the demo in below step
         

Run Demo with |realsense| Camera
---------------------------------

Execute the following script to launch the Follow-me application tutorial with gesture on the Aaeon robot:

   .. code-block::

      source /opt/ros/humble/setup.bash
      /opt/ros/humble/share/tutorial-follow-me-w-gesture/scripts/aaeon-follow-me-w-gesture.sh <Camera1 Serial number> < Camera2 Serial Number>


Camera1 serial number : Camera which is mounted to the bottom (used for tracking the target).

Camera2 serial Number : Camera mounted on the top (used for gesture recognition).
 
After executing the above command, you can observe that the robot is locating the target within a tracking radius (~0.5 - 0.7 m) and subsequently, following the moving target person as soon as he/she shows ``thumbs up``. The robot will stop as soon as ``thumbs down`` is showed or the target person moves away from the tracking radius.

.. note::

   There are reconfigurable parameters in `/opt/ros/humble/share/tutorial-follow-me-w-gesture/params` directory for |realsense| camera (`followme_adbscan_RS_params.yaml`). The user can modify parameters depending on the respective robot, sensor configuration and environments (if required) before running the tutorial.
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

   .. code-block::

      sudo chmod <xxx> /dev/dri/render128

- Failed to install |deb_pack|: Please make sure to run ``sudo apt update`` before installing the necessary |deb_packs|.

- You may stop the demo anytime by pressing ``ctrl-C``.

- If the robot rotates more than intended at each step, try reducing the parameter ``max_angular`` in the parameter file.

- For general robot issues, go to: :doc:`../../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.

- If the motor controller board does not start, restart the robot.
