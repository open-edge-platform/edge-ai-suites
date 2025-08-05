.. followme-with-gesture:

Follow-me with ADBSCAN, Gesture and Audio Control
=====================================================

This demo of the Follow-me algorithm shows a |p_amr| application for following a target person where the movement of the robot can be controlled by the person's location, hand gestures as well as audio command. The entire pipeline diagram can be found in :doc:`../index` page.
It takes point cloud sensor (2D Lidar/depth camera) as well as RGB camera image as inputs. These inputs are passed through |intel|-patented Adaptive DBScan and a deep-learning-based gesture recognition pipeline, respectively to publish motion command messages for a differential drive robot. It also takes recorded audio commands for starting and stopping the robot movement. Moreover, the demo is equipped with a text-to-speech synthesis model to narrate the robot's
activity over the course of its movement. 

This demo has been tested and validated on 13th Generation |core| processors with |xe| and 12th Generation |core| processors with |xe|.
This tutorial describes how to launch the demo in the `Gazebo` simulator. 

Getting Started
----------------


Install the |deb_packs|
^^^^^^^^^^^^^^^^^^^^^^^

Install ``ros-humble-followme-turtlebot3-gazebo`` and ``ros-humble-text-to-speech-pkg`` |deb_packs| from |intel| |p_amr| APT repository. ``ros-humble-followme-turtlebot3-gazebo`` is the wrapper package for the demo which will install all of the dependencies in the backend.

   .. code-block:: 

      sudo apt update
      sudo apt install ros-humble-followme-turtlebot3-gazebo ros-humble-text-to-speech-pkg

.. _pre-requisite:

Install Pre-requisite Libraries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install the pre-requisite modules for running the framework:
   
   .. code-block:: 

      source /opt/ros/humble/setup.bash
      pip install -r /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/requirements.txt

If you are under a proxy network, please make sure to use ``--proxy <http-proxy-url>`` with the ``pip install`` command.

.. _followme-gesture-audio-lidar:

Run Demo with 2D Lidar
----------------------------
Please make sure to source the ``/opt/ros/humble/setup.bash`` file at first before executing any command in a new terminal. You can get more details in :doc:`../../../../../gsg_robot/prepare-system` page.

Run the following commands one by one in five separate terminals:

1. Terminal 1: This command will open |ros| rviz2.

  .. code-block:: 

    rviz2 -d /opt/ros/humble/share/followme_turtlebot3_gazebo/rviz/followme_lidar.rviz

You will see the |ros| rviz2 with a panel for `Image` visualization. It will display the published RGB image in the simulated RGB camera.
   
  .. image:: ../../../../../images/rviz_display_follow_me.png

2. Terminal 2: This command will launch ``ros-humble-text-to-speech-pkg``.

  .. code-block:: 

    ros2 run text_to_speech_pkg text_to_speech_node.py --ros-args --params-file /opt/ros/humble/share/text_to_speech_pkg/config/text_to_speech_config.yaml 

You will see the |ros| node starting up and loading the parameter files for the underlying neural networks. This operation may take ~5-10 seconds depending on the system speed.
   
  .. image:: ../../../../../images/text_to_speech_launch_follow_me.png

3. Terminal 3: This command will launch `Gazebo`.

  .. code-block:: 

    export TURTLEBOT3_MODEL=waffle
    ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_audio_1.launch.py

You will see the `Gazebo` GUI with two simulated robots in an empty `Gazebo` world. We suggest to rescale and place the `Gazebo` and rviz panels side by side (like the following picture) for better visualization of the demo. 
   
  .. image:: ../../../../../images/follow_me_demo_gazebo_rviz.png


-  The green square robot is a guide robot (namely, the target), which will follow a pre-defined trajectory.

-  Gray circular robot is a `TurtleBot3 <https://emanual.robotis.com/docs/en/platform/turtlebot3/simulation/#gazebo-simulation>`__, which will follow the guide robot. |tb3| is equipped with a 2D Lidar and an |realsense| depth camera. In this demo, the 2D Lidar is selected as the point cloud input.

In this demo, we used a pre-defined trajectory for the guide robot and published gesture image as well as pre-recorded audio at different points of time to show `start`, `follow` and `stop` activities of the |tb3|.

4. Terminal 4: This command will launch the ``adbscan`` node, which will publish `twist` msg to the ``tb3/cmd_vel`` topic:

  .. code-block:: 

    ros2 run adbscan_ros2_follow_me adbscan_sub_w_gesture_audio --ros-args --params-file /opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_2D.yaml -r cmd_vel:=tb3/cmd_vel -p use_sim_time:=true

You will view the following information in the terminal. 

  .. image:: ../../../../../images/adbscan_screenshot_lidar.png

5. Terminal 5: This command will launch the pre-defined trajectory for the guide robot as well as the simulated gesture images and pre-recorded audio publisher nodes:

  .. code-block:: 

    ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_audio_2.launch.py

  .. Note::

    If you are running the demo in 13th Generation |core| processors with |xe| (known as Raptor Lake-P), please replace the commands in terminal 5 with the following:

    .. code-block:: 

      ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_audio_2.launch.py soc:='rpl'

This command will display the following information:

  .. image:: ../../../../../images/publisher_screenshot.png

As soon as the last command is executed, you will view that the guide robot starts moving towards |tb3|.
In order to start the |tb3|, condition 1 and either one of the conditions 2 or 3 from the following list need to be true:

1.  The target (guide robot) is located within the tracking radius (a reconfigurable parameter in the parameter file: `/opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_2D.yaml`) of the |tb3|.

2.  The gesture (visualized in the ``/image`` topic in |ros| rviz2) of the target is ``thumbs up``.

3.  The detected audio from the recording is ``Start Following``.


The stop condition for the |tb3| is fulfilled when any one of the following conditions holds true:

1.  The target (guide robot) moves to a distance of more than the tracking radius (a reconfigurable parameter in the parameter file: `/opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_2D.yaml`) from the |tb3|.

2.  The gesture (visualized in the ``/image`` topic in |ros| rviz2) of the target is ``thumbs down``.

3.  The detected audio from the recording is ``Stop Following``.

The demo will narrate the detected gesture, audio and target location during the `start` and `stop` activity of the |tb3|.

  .. Note::

    The current version of the demo only supports ``Start``, ``Stop``, ``Start Following`` and ``Stop Following`` audio commands. If the detected audio does not match any of the supported commands, the audio control will be ignored and the movement of the robot will be determined by the remaining criteria. Similarly, hand gesture control will be ignored if it does not match ``thumbs up`` or ``thumbs down``. Thereby, any undesired manipulation of the robot is blocked.

.. _followme-gesture-audio-realsense:

Run Demo with |realsense| Camera
---------------------------------------

Please make sure to source the ``/opt/ros/humble/setup.bash`` file at first before executing any command in a new terminal. You can get more details in :doc:`../../../../../gsg_robot/prepare-system` page.

Execute the following commands one by one in three separate terminals:

1. Terminal 1: This command will open |ros| rviz2.

  .. code-block:: 

    rviz2 -d /opt/ros/humble/share/followme_turtlebot3_gazebo/rviz/followme_lidar.rviz

You will see |ros| rviz2 GUI with a panel for `Image` visualization. It will display the published RGB image in the simulated RGB camera.
   
  .. image:: ../../../../../images/rviz_display_follow_me.png

2. Terminal 2: This command will launch ``ros-humble-text-to-speech-pkg``.

  .. code-block:: 

    ros2 run text_to_speech_pkg text_to_speech_node.py --ros-args --params-file /opt/ros/humble/share/text_to_speech_pkg/config/text_to_speech_config.yaml 

You will see the |ros| node starting up and loading the parameter files for the underlying neural networks. This operation may take ~5-10 seconds depending on the system speed.
   
  .. image:: ../../../../../images/text_to_speech_launch_follow_me.png

3. Terminal 3: This command will launch `Gazebo`.

  .. code-block:: 

    export TURTLEBOT3_MODEL=waffle
    ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_audio_1.launch.py

4. Terminal 4: This command will launch the ``adbscan`` node, which will publish `twist` msg to the ``tb3/cmd_vel`` topic:

  .. code-block:: 

    ros2 run adbscan_ros2_follow_me adbscan_sub_w_gesture_audio --ros-args --params-file /opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_RS.yaml -r cmd_vel:=tb3/cmd_vel -p use_sim_time:=true

In this instance, we execute ``adbscan`` with the parameter file for |realsense| camera input: ``adbscan_sub_RS.yaml``.

You will view the following information in the terminal. 

  .. image:: ../../../../../images/adbscan_screenshot.png

5. Terminal 5: This command will launch the pre-defined trajectory for the guide robot as well as the simulated gesture images and pre-recorded audio publisher nodes:

  .. code-block:: 

    ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_audio_2.launch.py

  .. Note::

    If you are running the demo in 13th Generation |core| processors with |xe| (known as Raptor Lake-P), please replace the commands in terminal 5 with the following:

    .. code-block:: 

      ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_audio_2.launch.py soc:='rpl'

After running all of the above commands, you will observe similar behavior of the |tb3| and guide robot in the `Gazebo` GUI as in :ref:`followme-gesture-audio-lidar`.

.. note::

   There are reconfigurable parameters in `/opt/ros/humble/share/adbscan_ros2_follow_me/config/` directory for both LIDAR (`adbscan_sub_2D.yaml`) and |realsense| camera (`adbscan_sub_RS.yaml`). The user can modify the parameters depending on the respective robot, sensor configuration and environments (if required) before running the tutorial.
   Find a brief description of the parameters in the following table.

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

.. _troubleshooting:

Troubleshooting
----------------------------

- Failed to install |deb_pack|: Please make sure to run ``sudo apt update`` before installing the necessary |deb_packs|.

- Please make sure to prepare your environment before executing |ros| commands in a new terminal. You can find the instructions in :doc:`../../../../../gsg_robot/prepare-system` page.

- You can stop the demo anytime by pressing ``ctrl-C``. If the `Gazebo` simulator freezes or does not stop, please use the following command in a terminal:

   .. code-block::

      sudo killall -9 gazebo gzserver gzclient

- We used `simpleaudio` python library to playback audio. The necessary dependencies are installed in the :ref:`pre-requisite` step. Please make sure that the system microphones are available and unmuted in order to listen to played audio during the demo.



