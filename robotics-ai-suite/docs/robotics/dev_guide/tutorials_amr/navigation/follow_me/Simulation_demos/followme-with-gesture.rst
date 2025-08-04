.. followme-with-gesture:

Follow-me with ADBSCAN and Gesture Control
====================================================

This demo of the Follow-me algorithm shows a |p_amr| application for following a target person where the movement of the robot can be controlled by the person's location and hand gestures. The entire pipeline diagram can be found in :doc:`../index` page.
This demo contains only the ADBSCAN and Gesture recognition modules in the input-processing application stack. No text-to-speech synthesis module is present in the output-processing application stack. This demo has been tested and validated on 12th Generation |core| processors with |xe| (known as Alder Lake-P).
This tutorial describes how to launch the demo in `Gazebo` simulator. 

Getting Started
----------------


Install the |deb_pack|
^^^^^^^^^^^^^^^^^^^^^^^

Install ``ros-humble-followme-turtlebot3-gazebo`` |deb_pack| from |intel| |p_amr| APT repository. This is the wrapper package which will launch all of the dependencies in the backend.

   .. code-block::

      sudo apt update
      sudo apt install ros-humble-followme-turtlebot3-gazebo

Install Python Modules
^^^^^^^^^^^^^^^^^^^^^^^

This application uses `Mediapipe Hands Framework <https://mediapipe.readthedocs.io/en/latest/solutions/hands.html>`__
for hand gesture recognition. Install the following modules as a prerequisite for the framework:
   
   .. code-block::

      pip3 install mediapipe
      pip3 install numpy==1.24.3

.. _followme-gesture-lidar:

Run Demo with 2D Lidar
----------------------------

Run the following script to launch `Gazebo` simulator and |ros| rviz2.

   .. code-block::

      sudo chmod +x /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_lidar.sh
      /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_lidar.sh

You will see two panels side-by-side: `Gazebo` GUI on the left and |ros| rviz display on the right.
   
   .. image:: ../../../../../images/screenshot_followme_w_gesture_demo.jpg

-  The green square robot is a guide robot (namely, the target), which will follow a pre-defined trajectory.

-  Gray circular robot is a `TurtleBot3 <https://emanual.robotis.com/docs/en/platform/turtlebot3/simulation/#gazebo-simulation>`__, which will follow the guide robot. |tb3| is equipped with a 2D Lidar and a |realsense| depth camera. In this demo, the 2D Lidar is used as the input topic.

**Both** of the following conditions need to be fulfilled to start the |tb3|:

-  The target (guide robot) will be within the tracking radius (a reconfigurable parameter in `/opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_2D.yaml`) of the |tb3|.

-  The gesture (visualized in the ``/image`` topic in |ros| rviz2) of the target is ``thumbs up``.

The stop condition for the |tb3| is fulfilled when **either one** of the following conditions are true:

-  The target (guide robot) moves to a distance of more than the tracking radius (a reconfigurable parameter in `/opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_2D.yaml`) from the |tb3|.

-  The gesture (visualized in the ``/image`` topic in |ros| rviz2) of the target is ``thumbs down``.

.. _followme-gesture-realsense:

Run Demo with |realsense| Camera
---------------------------------------

Execute the following commands one by one in three separate terminals.

#. Terminal 1: This command will open `Gazebo` simulator and |ros| rviz2.

   .. code-block::

      sudo chmod +x /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_RS.sh
      /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_RS.sh

#. Terminal 2: This command will launch the ADBSCAN |deb_pack|. It runs the ADBScan node on the point cloud data to detect the location of the target.

   .. code-block::

      ros2 run adbscan_ros2_follow_me adbscan_sub_w_gesture --ros-args --params-file /opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_RS.yaml -r cmd_vel:=tb3/cmd_vel

#. Terminal 3: This command will run the gesture recognition package.

   .. code-block::

      ros2 run gesture_recognition_pkg traj_and_img_publisher_node.py --ros-args --params-file /opt/ros/humble/share/gesture_recognition_pkg/config/gesture_recognition.yaml

In this demo, |realsense| camera of the |tb3| is selected as the input point cloud sensor. After running all of the above commands,
you will observe similar behavior of the |tb3| and guide robot in the `Gazebo` GUI as in :ref:`followme-gesture-lidar` 

.. note::

   There are reconfigurable parameters in `/opt/ros/humble/share/adbscan_ros2_follow_me/config/` directory for both LIDAR (`adbscan_sub_2D.yaml`) and |realsense| camera (`adbscan_sub_RS.yaml`). The user can modify parameters depending on the respective robot, sensor configuration and environments (if required) before running the tutorial.
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

- Failed to install |deb_pack|: Please make sure to run ``sudo apt update`` before installing the necessary |deb_packs|.

- You can stop the demo anytime by pressing ``ctrl-C``. If the `Gazebo` simulator freezes or does not stop, please use the following command in a terminal:

   .. code-block::

      sudo killall -9 gazebo gzserver gzclient



