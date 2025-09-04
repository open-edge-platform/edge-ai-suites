|irobot_create3|
================

|irobot_create3| is a mobile robotics platform, which developers can use
to gain hands-on experience with the technologies and concepts that are
foundational to the field of autonomous mobile robots. This practical
understanding is invaluable for those looking to enter the robotics
industry or further their knowledge in this rapidly evolving field.

Before starting, review the |irobot_create3_documentation| to be able to
perform the configuration changes needed for the tutorial.

Prerequisites
-------------

Complete the :doc:`../../../gsg_robot/index` before continuing.


|irobot_create3| hardware extensions
------------------------------------

|irobot_create3| contains a compute unit running |ros| that provides
access to the on-board sensors and actuators. For this tutorial, the
following modifications have been applied to the robot:

 - two support layers added on top of the robot,

 - |intel| board mounted on the bottom layer,

 - |realsense| camera mounted on the front of the top layer and
   connected to a USB port on the |intel| board,

 - |slamtec_rplidar| 2D (|slamtec_rplidar_a3| or |slamtec_rplidar_a2m8|) sensor on a mount in the center of the
   top layer and connected to two USB ports on the |intel| board,

 - custom battery in the cargo bay to power the |intel| board and
   accessories, namely the camera and the lidar,

 - an Ethernet adapter connected to the |irobot_create3| adapter board
   and to the |intel| board,

 - a rear caster wheel attached to the cargo bay, as described in the
   `iRobot® Create® 3 Mechanical System
   <https://iroboteducation.github.io/create3_docs/hw/mechanical/>`__
   documentation.


.. figure:: ../../../images/iRobot/IAF1-iRobot-Create-3-MTL-Custom-setup-front-view-without-static-stand.jpg
   :width: 500px
   :align: center

   |irobot_create3| robot front view.

.. figure:: ../../../images/iRobot/IAF1-iRobot-Create-3-MTL-Custom-setup-back-view-2.jpg
   :width: 500px
   :align: center

   |irobot_create3| robot rear view.


|irobot_create3| software configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Update the robot to use the latest |l_ros| firmware and configure it
to access your WiFi network following the
`iRobot® Create® 3 Setup
<https://edu.irobot.com/create3-setup>`__ documentation.

With the robot connected to your WiFi network continue configuring it
using its web interface. Refer to the |irobot_create3_documentation| for the exact
steps to follow.

Wired (Ethernet) network
........................

The |intel| board and the compute unit of the |irobot_create3| should be
connected using an Ethernet adapter with a USB Type-C connector. The
USB Type-C plug should be connected to the adapter board of the
|irobot_create3|, while the |intel| board should be connected to the
Ethernet adapter using an RJ-45 cable.

.. figure:: ../../../images/iRobot/iRobot-Create-3-Ethernet-connection.jpg
   :width: 600px
   :align: center

   Ethernet via USB connection between |irobot_create3|  adapter board
   and |intel| board.

The |irobot_create3| robot is configured to use the address
``192.168.186.2/24`` on the USB interface. You can change the network
part of the address by following the instructions on page
|irobot_create3_webserver_set_wired_subnet|.

On the |intel| board, the network interface connected to the robot
has to be configured with a static IP address of the same subnet.

NTP server
..........

Time synchronization is very important in |ros|. For this reason, the
|irobot_create3| includes an NTP server, which can be configured as described on page
`iRobot® Create® 3 Webserver - Edit ntp.conf
<https://iroboteducation.github.io/create3_docs/webserver/edit-ntp-conf/>`__.

Alternatively, you can set up an NTP server on the |intel| board by following
the |irobot_create3| documentation `Set up NTP on compute board
<https://iroboteducation.github.io/create3_docs/setup/compute-ntp/>`__.
Use the IP address of the Ethernet interface connected to the robot.

|ros| Middleware (RMW) Configuration & Fast DDS discovery server
................................................................

To define what |ros| middleware implementation shall be used by the
|irobot_create3|, follow the configuration guidelines on page
|irobot_create3_webserver_application|.
Set the RMW_IMPLEMENTATION option to ``rmw_fastrtps_cpp``, as shown in
the figure below.

.. figure:: ../../../images/iRobot/iRobot-create3-ROS-configuration.png
   :align: center

   |irobot_create3| |l_ros| application configuration page. On this
   robot the |irobot_create3_webserver_set_wired_subnet|
   is set to ``192.168.99.2``, Fast DDS discovery server is enabled
   and runs on the |intel| board reachable at IP ``192.168.99.10``
   over the Ethernet connection. |ros| Domain ID is set but it is not
   used when the discovery server is enabled.

To speed up node discovery, enable the
`iRobot® Create® 3 Fast DDS Discovery Server
<https://iroboteducation.github.io/create3_docs/setup/discovery-server/>`__.
Use the IP address set above for the |intel| board on the USB
connection to the |irobot_create3| as the Fast DDS Discovery Server IP
address.

.. note::

   When the discovery server is enabled, the ``ROS_DOMAIN_ID`` is not used.

Robot namespace
...............

Set a |ros| namespace (e.g., ``/robot2``) for your robot, as described on page
|irobot_create3_webserver_application|. This value should be passed to the
launch file as argument ``irobot_ns``.

|lp_amr| Tutorials based on the |irobot_create3|
---------------------------------------------------

.. toctree::
   :maxdepth: 1

   ../navigation/wandering_app/wandering-irobot-tutorial
   ../navigation/follow_me/Tutorials/followme-on-irobot
