# Install the Autonomous Mobile Robot on Jackal Robot's Onboard Computer

This section shows how to install the Autonomous Mobile Robot with the
ROS 2 middleware and the Clearpath Robotics ecosystem, on
the Clearpath Robotics Jackal robot's onboard computer.

The Jackal robot is equipped with an onboard
computer that has a pre-installed Canonical Ubuntu 22.04 LTS OS,
ROS 2 Humble distribution, and the Clearpath Robotics software packages.

Intel recommends using the pre-installed software for the initial bring-up
of your Jackal robot. During the initial bring-up, you must update
the firmware of the MCU; see the
[Robot Installation](https://docs.clearpathrobotics.com/docs/ros/installation/robot/)
page of the Clearpath Robotics documentation.

Intel recommends creating a backup of the default software installation
or replace the pre-installed SATA M.2 SSD with an empty storage device,
before continuing with the next steps.

## Install ROS 2 Humble Distribution and Autonomous Mobile Robot

1. To install the ROS 2 Humble distribution and the Autonomous Mobile Robot on the
Clearpath Robotics Jackal robot, see the
[GSG Robot Guide](../../../../gsg_robot/index.rst)` of the Autonomous Mobile Robot.

1. Create an account with the username ``administrator``when
installing the Canonical Ubuntu OS, or create and set its group membership
as follows:

   ```bash
   sudo adduser administrator
   sudo usermod -a -G sudo administrator
   ```

## Install the Clearpath Robotics Software Packages

1. Install the ROS 2 development tools, which comprises the compilers
and other tools to build ROS 2 packages. See the official
[ROS 2 Installation Instructions](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html):

   ```bash
   sudo apt-get install ros-dev-tools
   ```

## Install the Clearpath Robotics Software Packages.

See the [Package Install](https://docs.clearpathrobotics.com/docs/ros/installation/robot/#package-install)
section of the Clearpath Robotics documentation. You can install the software through one of these methods:

- [Option 1: Install Script](https://docs.clearpathrobotics.com/docs/ros/installation/robot/#option-1-install-script),
  which uses an automated installer.
- [Option 2: Manual Source Install](https://docs.clearpathrobotics.com/docs/ros/installation/robot/#option-2-manual-source-install),
  which provides detailed instructions on how to install the software with a higher flexibility.

## Create Your Robot Configuration

This section shows how to create the ``robot.yaml`` configuration
file for your Jackal robot with the Intel® RealSense™ camera D435i. Ensure
to complete the
[Install the Clearpath Robotics Software Packages](#install-the-clearpath-robotics-software-packages)
steps.

### Identify the Serial Number of your Intel® RealSense™ Camera

You need to include the serial number of the Intel® RealSense™ camera to the
``robot.yaml`` file.

> **Note:** Do not run ``lsusb -v`` to get the serial number because the serial number displayed might differ from the true serial number.

1. To get the serial number, connect the camera
   to the onboard computer of the Jackal robot and run:

   ```bash
   ros2 launch realsense2_camera rs_launch.py
   ```

   The output of this command will print the serial number. The serial
   number of the camera in the example below is ``207522xxxx38`` (some digits
   are masked here to preserve confidentiality).

   ```console
   [realsense2_camera_node-1] [INFO] [1709051840.999128954] [camera.camera]: RealSense ROS v4.54.1
   [realsense2_camera_node-1] [INFO] [1709051840.999193090] [camera.camera]: Built with LibRealSense v2.55.0
   [realsense2_camera_node-1] [INFO] [1709051840.999200850] [camera.camera]: Running with LibRealSense v2.55.0
   [realsense2_camera_node-1] [INFO] [1709051841.005234011] [camera.camera]: Device with serial number 207522xxxx38 was found.
   ```

1. Stop the command by pressing ``Ctrl-c``.

### Create your Robot YAML File

1. To configure the ``robot.yaml`` file for your Jackal robot, see the
[Robot YAML Overview](https://docs.clearpathrobotics.com/docs/ros/config/yaml/overview/)
section of the Clearpath Robotics documentation.

1. You can use the example configuration
[j100_sample.yaml](https://github.com/clearpathrobotics/clearpath_config/blob/main/clearpath_config/sample/j100/j100_sample.yaml)
in the Clearpath Robotics [configuration repository](https://github.com/clearpathrobotics/clearpath_config):

   Edit the ``serial_number`` and ``system`` sections in the j100_sample.yaml file as follows:

   - Change the ``serial_number`` to the serial
     number of your robot, for example ``j100-1234``.
   - In the ``system/hosts`` section, change the ``hostname`` to the
     hostname of the onboard computer of your Jackal robot.
   - In the ``system/hosts`` section, change the ``ip`` address to the
     IP address of your Jackal robot, either a static address or
     a dynamic address that is assigned by the router of your network.
   - In the ``system/ros2`` section, change the ``namespace`` string.
     While the Clearpath Robotics default configuration usually defines
     a namespace for the ROS 2 topics, Intel recommends using an empty
     namespace as used in the Autonomous Mobile Robot tutorials. An empty
     namespace is indicated by a slash character: ``namespace: /``
   - In the ``system/ros2`` section, add the ``domain_id`` entry and set it
     to a value that does not conflict with the ``ROS_DOMAIN_ID`` of
     other ROS 2 installations in your neighborhood. The value that you
     use here will be propagated into the ``/etc/clearpath/setup.bash`` script,
     whose execution has been added to your ``~/.basrc`` script when you
     executed one of the installation options in the
     [Install](#install-the-clearpath-robotics-software-packages) section.
     The``ROS_DOMAIN_ID`` environment variable will be
     set to the value you defined here.
   - If you have used the manual installation option in the
     [Install Clearpath Software Packages](#install-the-clearpath-robotics-software-packages)
     section, add the ``workspaces`` entry
     to the ``system/ros2`` section. This entry provides a list of setup
     scripts that need to be sourced. Provide the path to the ``setup.bash``
     script of the workspace that was created when you executed the steps in the
     [Option 2: Manual Source Install](https://docs.clearpathrobotics.com/docs/ros/installation/robot/#option-2-manual-source-install)
     section. The path of this script is
     ``/home/administrator/clearpath_ws/install/setup.bash``

   Details on these configuration entries are provided on the
   [System](https://docs.clearpathrobotics.com/docs/ros/config/yaml/system/)
   section of the Clearpath Robotics documentation. As an example,
   the following listing shows the first sections of the``robot.yaml`` file:

   > ```yaml
   > serial_number: j100-1234
   > version: 0
   > system:
   >   hosts:
   >     - hostname: jackal-cfls-01
   >       ip: 192.168.1.78
   >   ros2:
   >     namespace: /
   >     domain_id: 68
   >     workspaces:
   >       - /home/administrator/clearpath_ws/install/setup.bash
   > platform:
   >   ...
   > ```

1. Copy the ``robot.yaml`` file
   to the ``/etc/clearpath/`` folder on the onboard computer of your
   Jackal robot.

1. If your ``~/.bashrc`` script defines a ``ROS_DOMAIN_ID`` environment variable,
   remove this definition. This variable will be
   set by the ``/etc/clearpath/setup.bash`` script according to the ``domain_id``
   value that you have defined in the ``robot.yaml`` file.

After you have installed the Clearpath Robotics software packages and
configured your ``robot.yaml`` file, you can run
``ros2 node list`` and ``ros2 topic list`` to verify that
the Clearpath Robotics services have started the Jackal-specific ROS 2
nodes, so that the related ROS 2 topics are published.

### Add your Intel® RealSense™ Camera D435i to the Robot YAML File

You need to define a camera in the ``sensors`` section of your robot.yaml file.

1. The [Sensors/Cameras](https://docs.clearpathrobotics.com/docs/ros/config/yaml/sensors/cameras)
   section of the Clearpath Robotics documentation shows an example of the
   data structure that defines an Intel® RealSense™ camera instance.

   Intel recommends adding the following ``camera`` configuration as the first device in the
   ``sensors`` section. This configuration has been tested with
   the Autonomous Mobile Robot:

   > ```yaml
   > sensors:
   >   camera:
   >   - model: intel_realsense
   >     urdf_enabled: true
   >     launch_enabled: true
   >     parent: base_link
   >     xyz: [0.21, 0.0, 0.19]
   >     rpy: [0.0, 0.0, 0.0]
   >     ros_parameters:
   >       camera:
   >         camera_name: camera_0
   >         device_type: d435i
   >         serial_no: "207522xxxx38"
   >         enable_color: true
   >         rgb_camera.profile: 640,480,30
   >         enable_depth: true
   >         depth_module.profile: 640,480,30
   >         pointcloud.enable: true
   >         enable_infra1: true
   >         align_depth.enable: true
   >         enable_sync: true
   >         initial_reset: true
   > ```

   In comparison to the example data structure in the Clearpath Robotics documentation,
   the following items were changed:

   - The ``xyz`` position of the ``camera`` joint, relative to the ``base_link``
     has been set to ``[0.21, 0.0, 0.19]``. This means that the camera sits above
     the front fender of the Jackal robot as shown in the following figure:

     ![jackal_with_camera2](../../../../images/jackal_with_camera2.png)

     This figure is rendered through the rviz2 tool using the TF data
     published by the Clearpath Robotics services running on the robot.

   - The ``device_type`` has been set to ``d435i``.

   - The ``serial_no`` has been replaced with the actual serial number of the
     camera, which can be identified as described in the
     [Identify Intel RealSense Camera Serial Number](#identify-the-serial-number-of-your-intel-realsense-camera) section.

   - The following features have been enabled:
     ``enable_infra1``, ``align_depth.enable``, ``enable_sync``, and ``initial_reset``.

1. Copy the ``robot.yaml`` file to the ``/etc/clearpath/`` folder on the onboard computer
   of your Jackal robot.

1. Reboot the robot to propagate the new configuration.

## Verify the Robot Configuration

### Verify the Frames of the TF2 Tree

1. If not already installed, install the ROS2 TF2 Tools:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   sudo apt install ros-jazzy-tf2-tools
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   sudo apt install ros-humble-tf2-tools
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

1. Verify that the robot state publisher communicates the correct TF2 tree:

   ```bash
   ros2 run tf2_tools view_frames
   ```

   This command listens to the frames that are broadcast over the ROS 2
   middleware, and generates a PDF file that shows how the robot's frames are connected.
   Open the PDF file and verify that the TF2 tree contains the ``camera_0_link``
   and its children, as shown in the following figures:

   ![frames_jackal_2024-02-28](../../../../images/frames_jackal_2024-02-28.png)

1. Complete TF2 tree of the Jackal robot with Intel® RealSense™ camera.
   To increase the figure, right-click on the image and open the image
   in a new browser tab. The following figure shows the TF2 tree of the Jackal robot,
   with a detailed view on the camera_0_link:

   ![frames_jackal_camera_2024-02-28](../../../../images/frames_jackal_camera_2024-02-28.png)

### Verify the ROS 2 Topics

1. Run

   ```bash
   ros2 topic list
   ```

1. Verify that the required ROS 2 topics are published:

   > **Note:** The names of the camera-related topics depend on the version of the
   > ``ros-humble-realsense2-camera`` package on your system. The following list was
   > created on a system with package version 4.55.

   ```console
   /cmd_vel
   /diagnostics
   /diagnostics_agg
   /diagnostics_toplevel_state
   /joint_state_broadcaster/transition_event
   /joy_teleop/cmd_vel
   /joy_teleop/joy
   /joy_teleop/joy/set_feedback
   /parameter_events
   /platform/bms/state
   /platform/cmd_vel_unstamped
   /platform/dynamic_joint_states
   /platform/emergency_stop
   /platform/joint_states
   /platform/mcu/status
   /platform/mcu/status/power
   /platform/mcu/status/stop
   /platform/motors/cmd_drive
   /platform/motors/feedback
   /platform/odom
   /platform/odom/filtered
   /platform/wifi_connected
   /platform/wifi_status
   /platform_velocity_controller/transition_event
   /rc_teleop/cmd_vel
   /robot_description
   /rosout
   /sensors/camera_0/camera/aligned_depth_to_color/camera_info
   /sensors/camera_0/camera/aligned_depth_to_color/image_raw
   /sensors/camera_0/camera/aligned_depth_to_color/image_raw/compressed
   /sensors/camera_0/camera/aligned_depth_to_color/image_raw/compressedDepth
   /sensors/camera_0/camera/aligned_depth_to_color/image_raw/theora
   /sensors/camera_0/camera/aligned_depth_to_infra1/camera_info
   /sensors/camera_0/camera/aligned_depth_to_infra1/image_raw
   /sensors/camera_0/camera/aligned_depth_to_infra1/image_raw/compressed
   /sensors/camera_0/camera/aligned_depth_to_infra1/image_raw/compressedDepth
   /sensors/camera_0/camera/aligned_depth_to_infra1/image_raw/theora
   /sensors/camera_0/camera/color/camera_info
   /sensors/camera_0/camera/color/image_raw
   /sensors/camera_0/camera/color/image_raw/compressed
   /sensors/camera_0/camera/color/image_raw/compressedDepth
   /sensors/camera_0/camera/color/image_raw/theora
   /sensors/camera_0/camera/color/metadata
   /sensors/camera_0/camera/depth/camera_info
   /sensors/camera_0/camera/depth/color/points
   /sensors/camera_0/camera/depth/image_rect_raw
   /sensors/camera_0/camera/depth/image_rect_raw/compressed
   /sensors/camera_0/camera/depth/image_rect_raw/compressedDepth
   /sensors/camera_0/camera/depth/image_rect_raw/theora
   /sensors/camera_0/camera/depth/metadata
   /sensors/camera_0/camera/extrinsics/depth_to_color
   /sensors/camera_0/camera/extrinsics/depth_to_infra1
   /sensors/camera_0/camera/infra1/camera_info
   /sensors/camera_0/camera/infra1/image_rect_raw
   /sensors/camera_0/camera/infra1/image_rect_raw/compressed
   /sensors/camera_0/camera/infra1/image_rect_raw/compressedDepth
   /sensors/camera_0/camera/infra1/image_rect_raw/theora
   /sensors/camera_0/camera/infra1/metadata
   /sensors/camera_0/color/image
   /sensors/camera_0/depth/image
   /sensors/camera_0/points
   /sensors/gps_0/nmea_sentence
   /sensors/imu_0/data
   /sensors/imu_0/data_raw
   /sensors/imu_0/magnetic_field
   /sensors/lidar2d_0/diagnostics
   /sensors/lidar2d_0/laser_status
   /sensors/lidar2d_0/scan
   /sensors/lidar2d_1/diagnostics
   /sensors/lidar2d_1/laser_status
   /sensors/lidar2d_1/scan
   /sensors/lidar3d_0/diagnostics
   /sensors/lidar3d_0/points
   /sensors/lidar3d_0/scan
   /sensors/lidar3d_0/velodyne_packets
   /sensors/lidar3d_0/velodyne_points
   /set_pose
   /tf
   /tf_static
   /twist_marker_server/cmd_vel
   /twist_marker_server/feedback
   /twist_marker_server/update
   ```

1. To see the installed package version on your board, run:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   ```bash
   apt show ros-jazzy-realsense2-camera
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   ```bash
   apt show ros-humble-realsense2-camera
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

   The following table shows how the names of the camera-related topics
   depend on the package version.

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1hide_directive-->

   |Version of ``ros-jazzy-realsense2-camera``|Camera-related topics start with|
   |---|---|
   |4.55|``/sensors/camera_0/camera/``|
   |4.54|``/sensors/camera_0/``|

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: tab2hide_directive-->

   |Version of ``ros-humble-realsense2-camera``|Camera-related topics start with|
   |---|---|
   |4.55|``/sensors/camera_0/camera/``|
   |4.54|``/sensors/camera_0/``|

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

## Jackal Troubleshooting

If the output of the ``ros2 topic list`` command does not show any topics,
verify that you are logged in as the ``administrator`` and
check that the ``ROS_DOMAIN_ID`` environment variable contains the value
that is defined in your ``/etc/clearpath/robot.yaml`` file
under the ``system/ros2/domain_id`` entry.

If the output of the ``ros2 topic list`` command shows some missing
ROS 2 topics (see the [verify ROS topics](#verify-the-ros-2-topics) section for a list of topics),
there might be an issue with your installation of the Clearpath Robotics
services.

In this case, check whether the required services are
up and running. These services are responsible for parsing the ``robot.yaml``
file and for starting the required ROS 2 nodes:

```bash
sudo systemctl status clearpath-platform.service clearpath-sensors.service clearpath-robot.service
```

If any of these services are not active (running), check whether
the systemd journal shows any error messages:

```bash
sudo journalctl -b | grep clearpath
```

## References

- [Clearpath Robotics - Jackal Unmanned Ground Vehicle Overview](https://clearpathrobotics.com/jackal-small-unmanned-ground-vehicle/)
- [Clearpath Robotics - Jackal Unmanned Ground Vehicle User Manual](https://docs.clearpathrobotics.com/docs_robots/outdoor_robots/jackal/user_manual_jackal/)
- [Clearpath Robotics - Robot Installation](https://docs.clearpathrobotics.com/docs/ros/installation/robot/)
