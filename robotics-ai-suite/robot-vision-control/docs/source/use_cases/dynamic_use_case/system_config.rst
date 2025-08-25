
.. _preliminary_system_configuration:

Preliminary system configuration
================================

Camera pose and robot calibration
---------------------------------

Before first RVC Execution, we have to ensure a few parameters that has to match the physical setup:

- RVC must known the exact pose (i.e.: position and orientation) of the |realsense| camera as explained in :ref:`Camera pose calibration<camera_pose_calibration>`
- Prepare the robot for communication with the |Intel| platform as in :ref:`Universal Robot configuration<universal_robot_configuration>`
- The robot calibration parameters from the real robot must be extracted, as explained further in :ref:`Universal Robot Calibration Procedure<robot_calibration_procedure>`

.. _camera_pose_calibration:

Camera pose calibration
^^^^^^^^^^^^^^^^^^^^^^^


Before starting the Vision component, verify that the camera location matches the position 
and orientation specified in the file 

.. code-block:: bash

    rvc_dynamic_motion_controller_use_case/cameraurdf/d415<namespace>.xacro

.. note::

    Location might change according to installation procedure and the suffix `ipc` depends on the 
    ``namespace:=`` option, by default `ipc` in this case

The default content of this file is:

.. code-block:: xml

    <?xml version="1.0"?>

    <robot name="d415_camera" xmlns:xacro="http://ros.org/wiki/xacro">
    <xacro:arg name="use_nominal_extrinsics" default="false"/>
    <xacro:arg name="name" default="camera<namespace>"/>
    <xacro:arg name="use_mesh" default="true"/>
    <xacro:arg name="use_plug" default="true"/>
    <xacro:include filename="$(find realsense2_description)/urdf/_d415.urdf.xacro" />
    <link name="world" />
    <xacro:sensor_d415 parent="world" name="$(arg name)" use_mesh="$(arg use_mesh)" add_plug="$(arg use_plug)" use_nominal_extrinsics="$(arg use_nominal_extrinsics)" >
            <origin xyz="0.36 0.66 0.755" rpy="-3.141592654 1.570796327 -1.570796327"/>
    </xacro:sensor_d415>
    </robot>


The important part is 

.. code-block:: xml

    <origin xyz="0.36 0.66 0.755" rpy="-3.141592654 1.570796327 -1.570796327"/>

where the ``xyz`` triplet is expressed in meters, and the ``rpy`` is in radians and they express respectively
the cartesian coordinates of the base of the camera in reference to the ``world`` frame_id, which should 
coincide with the center of the base of the robot, if not modified.

These numbers are important because if not accurate, the robot will not go to the proper location when
picking the objects, as the detection is in reference system of the camera, and the system has to
transform it to robot reference system, and these numbers give the relation between the two systems


.. _universal_robot_configuration:

Universal Robot configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The real robot or the simulator has to be configured to accept 
connection from RVC and configure the RVC system for real time capabilities


Set up Universal Robots  \ |tm|  UR5e
--------------------------------------
 

This section discusses, in brief, the steps to set up Universal Robots&trade; UR5e.

.. note::
    For more details, refer to the 
    `Universal Robots repositories README <https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/foxy/README.md>`_ 
    to configure the robot.


Set up Private Local Network
-----------------------------

One of the key considerations coming from Universal Robots\ |tm| is that the network connection from the controlling AI running RVC and the robot should be on a direct Ethernet connection. In this demonstration, a private local network with a dedicated switch was setup with no other traffic on this network, which worked well.

Install external_control.urcap
------------------------------

Configure the URCaps for the robot and the Robotiq 2F-85 URCap. For details, refer to
`Connect to External Control via URCap <https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver#connect-to-external-control-via-urcap>`_.

After installing `external_control.urcap`, the screen, shown in the following figure, will be displayed.

.. image:: /images/html/URExternalControl.png
    :alt: UR External Control

.. note::

    Replace the IP in, the figure, with your Intel target private network connected to the robot.

.. note::

    Before starting the demonstration, make sure that the **Speed** slider, shown in the figure, is set around 70%. Even if the speed is set to above 70%, the robot will follow, however higher speed might damage the bolts that connect the base of the robot to the table. Do the same for the Rviz2 speed slider also.

Install Gripper URCaps
-----------------------------

The URCaps are available on the `Robotiq <https://robotiq.com/products/2f85-140-adaptive-robot-gripper?ref=nav_product_new_button>`_ website.

To download the latest Gripper URCaps, click **Download files**. From the left panel, click **Universal Robots**. Then, click **Software** > **Gripper Software**. Click **DOWNLOAD ZIP**.

Install these URCaps on the UR5e robot teach pendant using an USB key.

Restart the robot. Select **Program Robot** on the Welcome screen. Go to the **Installation** tab. Select **Gripper** listed under **URCaps**.

.. image:: /images/html/URRobotiqGripper.png
    :alt: UR Robotiq Gripper urcap


.. _robot_calibration_procedure:

Overwrite Model-specific Kinematics Parameters (Calibration)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There might be slight differences (variance) in the physical attributes of various robots. To address this issue, the robot is calibrated at the factory and the variance in these parameters are saved on the robot controller file system. Extract the kinematics parameters specific to your robot and overwrite the distributed parameters file to avoid the robot being sent elsewhere for accumulating errors on inverse kinematics computation due to this parameter variance.

For information on the Universal Robots\ |tm| calibration, refer to 
`README.md <https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/foxy/ur_calibration/README.md>`_

.. note::

    If the calibration parameters do not match with that of the real robot, the motion controller logs will show the following message:  

::

    [ros2_control_node-1] [INFO] [1665059043.476735447] [URPositionHardwareInterface]: Calibration checksum: 'calib_12788084448423163542'.
    [ros2_control_node-1] [ERROR] [1665059044.504667587] [URPositionHardwareInterface]: The calibration parameters of the connected robot don't match the ones from the given kinematics config file. Please be aware that this can lead to critical inaccuracies of tcp positions. Use the ur_calibration tool to extract the correct calibration from the robot and pass that into the description. See [https://github.com/UniversalRobots/Universal_Robots_ROS_Driver#extract-calibration-information] for details.

Calibration Example
"""""""""""""""""""""""


Execute:

.. code-block:: bash

    ros2 launch ur_calibration  calibration_correction.launch.py robot_ip:=<robot_ip> target_filename:=./thisur5e_kinematics.yaml


Make sure to overwrite the result file at:

`<urdriverinstallpath>/Universal_Robots_ROS2_Description/config/ur5e/thisur5e_kinematics.yaml`.

For example, in this demonstration, the result file is in:

`<urdescriptioninstallpath>/ur_description/config/ur5e/default_kinematics.yaml`

If everything is correct, you will see an information message instead of the error message.

::

    [ros2_control_node-1] [INFO] [1665059758.619735683] [URPositionHardwareInterface]: Calibration checksum: 'calib_10395257169742499224'.
    [ros2_control_node-1] [INFO] [1665059759.696690136] [URPositionHardwareInterface]: Calibration checked successfully.

Notice the different checksums.

Create Program
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To use the new URCaps, enabling the communication with the Intel Architecture RVC controller, create a new program on the teaching pendant and insert the **External Control** program node in the program tree.

.. image:: /images/html//URCreateProgram.png
    :alt: Create Program

.. note::

    Make sure that you have replaced Host IP with your IA RVC controller private network IP connected to the robot.
