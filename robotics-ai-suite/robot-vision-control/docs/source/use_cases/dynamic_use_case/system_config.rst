
.. _preliminary_system_configuration:

Preliminary System Configuration
================================


Before running RVC for the first time, ensure proper configuration has occurred:

- RVC must know the exact pose (i.e.: position and orientation) of the Intel® RealSense™ camera as explained in :ref:`camera integration<camera_integration>`
- Prepare the robot for communication with the Intel® platform as in :ref:`Universal Robots configuration<universal_robot_configuration>`
- The robot calibration parameters from the real robot must be extracted, as explained further in :ref:`Universal Robots Calibration Procedure<robot_calibration_procedure>`

- Camera
    - :ref:`Integration<camera_integration>`: These demonstrations support all |Realsense| |D4xx| cameras, though were designed with the D415.
- Universal Robots
    - :ref:`Communication<universal_robot_configuration>`: The robot must be properly configured to interface with the |Intel| platform
    - :ref:`Calibration Procedure<robot_calibration_procedure>`: Extract the robot's calibration parameters from the physical robot to ensure accurate operation.
    - :ref:`Home Pose<robots_home_pose>`: Verify and set the robot's default home pose according to its real-world configuration.

Camera
--------------------------------------
The RVC demonstrations assume use of the Intel® RealSense™ D415 camera. If you plan on exploring these exercises with a different
model from (e.g., D435, D455), the below modifications are required.

Before starting the Vision component, verify that the camera location matches the position
and orientation specified in the file

.. _camera_integration:

Integration
^^^^^^^^^^^
A .xacro file is an XML-based macro language that lets one define reusable components and parameters. With xacro, one
can construct shorter and more readable XML files by using macros that expand to larger XML expressions. This is used
to avoid repetition, improve readability, and make robot models configurable (e.g., by passing arguments).

    Location might change according to installation procedure and the suffix `ipc` depends on the
    ``namespace:=`` option, by default `ipc` in this case

The default content of this file is:

.. code-block:: xml

    <robot name="d455_camera" xmlns:xacro="http://ros.org/wiki/xacro">
        <xacro:arg name="use_nominal_extrinsics" default="false"/>
        <xacro:arg name="name" default="cameraipc0"/>
        <xacro:include filename="$(find realsense2_description)/urdf/_d455.urdf.xacro" />
        <link name="world" />
        <xacro:sensor_d455 parent="world" name="$(arg name)"  use_nominal_extrinsics="$(arg use_nominal_extrinsics)" >
            <origin xyz="0.36 0.66 0.755" rpy="-3.141592654 1.570796327 -1.570796327"/>
        </xacro:sensor_d455>
    </robot>


The important part is

.. code-block:: xml

    <origin xyz="0.36 0.66 0.755" rpy="-3.141592654 1.570796327 -1.570796327"/>

where the ``xyz`` triplet is expressed in meters, and the ``rpy`` is in radians and they express respectively
the cartesian coordinates of the base of the camera in reference to the ``world`` frame_id, which should
coincide with the center of the base of the robot, if not modified.

+---------------+--------------------------------------------+---------------------------------------------------------------+------------------------+
| Use Case      | Package                                    | Location                                                      | File Name              |
+===============+============================================+===============================================================+========================+
| Static        | rvc_static_motion_controller_use_case      | /rvc/src/rvc_static_motion_controller_use_case/cameraurdf     |  d415cameraipc.xacro   |
+---------------+--------------------------------------------+---------------------------------------------------------------+------------------------+
| Dynamic       | rvc_static_motion_controller_use_case arm  | /rvc/src/rvc_static_motion_controller_use_case/cameraurdf     |  d415cameraipc.xacro   |
+---------------+--------------------------------------------+---------------------------------------------------------------+------------------------+

.. note::

    Every component has an option to change the default namespace: ``namespace:=<namspace>`` which by default is "ipc". When specified, the components
    will only see other components if they have same namespaces and the associated .xacro files must be named as seen in the above table (e.g. ``d415camera<namespace>.xacro``)

.. _universal_robot_configuration:

Universal Robots Configuration
--------------------------------------


The real robot or the simulator has to be configured to accept
connection from RVC and configure the RVC system for real time capabilities


Set up Universal Robots UR5e Robot
--------------------------------------


This section briefly discusses the steps to set up the Universal Robots UR5e robot.

.. note::
    For more details, refer to the
    `Universal Robots repositories README <https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/foxy/README.md>`_
    to configure the robot.


Set up Private Local Network
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



One of the key considerations with Universal Robots is that the network connection between the controlling AI running RVC and the robot must be a direct Ethernet connection.

Install external_control.urcap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


Configure the URCaps for the robot and the Robotiq 2F-85 URCap. For details, refer to
`Connect to External Control via URCap <https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver#connect-to-external-control-via-urcap>`_.

After installing `external_control.urcap`, the screen, shown in the following figure, will be displayed.

.. image:: images/html/URExternalControl.png
    :alt: UR External Control

.. note::

    Replace the IP in the figure with your Intel target private network IP connected to the robot.

.. note::

    Before starting the demonstration, make sure that the **Speed** slider, shown in the figure, is set around 70%. Even if the speed is set above 70%, the robot will operate; however, higher speeds might damage the bolts that connect the base of the robot to the table. Do the same for the Rviz2 speed slider as well.

Install Gripper URCaps
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


The URCaps are available on the `Robotiq <https://robotiq.com/products/2f85-140-adaptive-robot-gripper?ref=nav_product_new_button>`_ website.

To download the latest Gripper URCaps, click **Download files**. From the left panel, click **Universal Robots**. Then, click **Software** > **Gripper Software**. Click **DOWNLOAD ZIP**.

Install these URCaps on the UR5e robot teach pendant using a USB drive.

Restart the robot. Select **Program Robot** on the Welcome screen. Go to the **Installation** tab. Select **Gripper** listed under **URCaps**.

.. image:: images/html/URRobotiqGripper.png
    :alt: UR Robotiq Gripper urcap


.. _robot_calibration_procedure:

Overwrite Model-specific Kinematics Parameters (Calibration)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There might be slight differences (variance) in the physical attributes of various robots. To address this issue, the robot is calibrated at the factory and the variance in these parameters is saved on the robot controller file system. Extract the kinematics parameters specific to your robot and overwrite the distributed parameters file. This avoids the robot accumulating errors in inverse kinematics computation due to parameter variance.

For information on the Universal Robots robot calibration, refer to
`README.md <https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/foxy/ur_calibration/README.md>`_

.. note::

    If the calibration parameters do not match with that of the real robot, the motion controller logs will show the following message:

::

    [ros2_control_node-1] [INFO] [1665059043.476735447] [URPositionHardwareInterface]: Calibration checksum: 'calib_12788084448423163542'.
    [ros2_control_node-1] [ERROR] [1665059044.504667587] [URPositionHardwareInterface]: The calibration parameters of the connected robot don't match the ones from the given kinematics config file. Be aware that this can lead to critical inaccuracies of tcp positions. Use the ur_calibration tool to extract the correct calibration from the robot and pass that into the description. See [https://github.com/UniversalRobots/Universal_Robots_ROS_Driver#extract-calibration-information] for details.

Calibration Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



Execute:

.. code-block:: bash

    ros2 launch ur_calibration  calibration_correction.launch.py robot_ip:=<robot_ip> target_filename:=./thisur5e_kinematics.yaml


Make sure to overwrite the result file at:

`<urdriverinstallpath>/Universal_Robots_ROS2_Description/config/ur5e/thisur5e_kinematics.yaml`.

For example, in this demonstration, the result file is in:

`<urdescriptioninstallpath>/ur_description/config/ur5e/default_kinematics.yaml`

If everything is correct, you will see an informational message instead of the error message.

::

    [ros2_control_node-1] [INFO] [1665059758.619735683] [URPositionHardwareInterface]: Calibration checksum: 'calib_10395257169742499224'.
    [ros2_control_node-1] [INFO] [1665059759.696690136] [URPositionHardwareInterface]: Calibration checked successfully.

Notice the different checksums.

Create Program
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To use the new URCaps, enabling the communication with the Intel® architecture RVC controller, create a new program on the teaching pendant and insert the **External Control** program node in the program tree.

.. image:: images/html//URCreateProgram.png
    :alt: Create Program

.. note::

    Make sure that you have replaced Host IP with your IA RVC controller private network IP connected to the robot.






.. _robots_home_pose:

Robot Home Pose
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We strongly recommend positioning the physical robot, as seen below, prior to executing any of the provided use cases.
This ensures that the robot begins from a well-defined and safe reference configuration, allowing the calibration parameters
and motion sequences to align precisely with the expectations of the RVC framework. Always verify that the robot is
correctly homed before initiating any automated behavior.

+----------+---------------+
| Joint    | Degrees       |
+==========+===============+
| Base     | 122°          |
+----------+---------------+
| Shoulder | -100°         |
+----------+---------------+
| Elbow    | 104°          |
+----------+---------------+
| Wrist 1  | 0°            |
+----------+---------------+
| Wrist 2  | 80°           |
+----------+---------------+
| Wrist 3  | 0°            |
+----------+---------------+

.. image:: images/html/sethomeposition.png
   :alt: setting home position
