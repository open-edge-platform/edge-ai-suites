
|irobot_create3| Wandering tutorial
-----------------------------------

This tutorial presents the Wandering application running on an
|irobot_create3| mobile robotics platform extended with an |intel|
compute board, an |realsense| camera and a |slamtec_rplidar| 2D lidar sensor.

The tutorial uses the |realsense| camera and the |slamtec_rplidar| 2D
lidar sensor for both mapping with RTAB-Map and navigation with Nav2.
For navigation, |intel| :doc:`ground floor segmentation
<../../../../dev_guide/tutorials_amr/perception/pointcloud-groundfloor-segmentation>`
is used for segmenting ground level and remove it from the |realsense|
camera pointcloud.

Watch the video for a demonstration of the |irobot_create3| navigating
in a testing playground:

.. video:: ../../../../videos/irobot-create3-demo-wandering-rviz.mp4
   :preload: none
   :width: 900

Getting Started
-------------------------------------------

Prerequisites
^^^^^^^^^^^^^

- Assemble your robotic kit following the instructions :doc:`irobot-create3 <../../developer_kit/irobot-create3-robot>`

- Complete the :doc:`../../../../gsg_robot/index` before continuing.

|intel| board connected to |irobot_create3|
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Follow the instructions on page
`iRobot® Create® 3 - Network Recommendations
<https://iroboteducation.github.io/create3_docs/setup/network-config/>`__
to set up an Ethernet over USB connection and to configure the network
device on the |intel| board.
Use an IP address of the same subnet as used on the |irobot_create3|.

Check that the |irobot_create3| is reachable over the Ethernet
connection. Output on the robot with the configuration from the image
above:

.. code-block:: bash

   $ ping -c 3 192.168.99.2
   PING 192.168.99.2 (192.168.99.2) 56(84) bytes of data.
   64 bytes from 192.168.99.2: icmp_seq=1 ttl=64 time=1.99 ms
   64 bytes from 192.168.99.2: icmp_seq=2 ttl=64 time=2.31 ms
   64 bytes from 192.168.99.2: icmp_seq=3 ttl=64 time=2.02 ms

   --- 192.168.99.2 ping statistics ---
   3 packets transmitted, 3 received, 0% packet loss, time 2004ms
   rtt min/avg/max/mdev = 1.989/2.105/2.308/0.144 ms

Install the ``ros-humble-wandering-irobot-tutorial`` package on the
|intel| board connected to the robot.

.. code-block:: bash

   apt install ros-humble-wandering-irobot-tutorial

Start the discovery server in a new terminal:

.. code-block:: bash

   fastdds discovery --server-id 0

In a new terminal set the environment variables for |ros| to use the
discovery server:

.. code-block:: bash

   export ROS_DISCOVERY_SERVER=127.0.0.1:11811
   export ROS_SUPER_CLIENT=true
   unset ROS_DOMAIN_ID

Check that the setup is correct by listing the |ros| topics provided
by the robot:

.. code-block:: bash

   ros2 topic list


The |irobot_create3| topics should be listed:

.. code-block:: bash

   /parameter_events
   /robot2/battery_state
   /robot2/cliff_intensity
   /robot2/cmd_audio
   /robot2/cmd_lightring
   /robot2/cmd_vel
   ...
   /robot2/tf
   /robot2/tf_static
   /robot2/wheel_status
   /robot2/wheel_ticks
   /robot2/wheel_vels
   /rosout


.. note::

   If only ``/parameter_events`` and ``/rosout`` topics are listed then
   the communication between the robot and the |intel| board is not
   working. Check the |irobot_create3_documentation| to troubleshoot
   the issue.

Start the tutorial using its launch file; provide the namespace set on
the robot in the argument ``irobot_ns``:

.. code-block:: bash

   ros2 launch wandering_irobot_tutorial wandering_irobot.launch.py irobot_ns:=/robot2

To use ``ros2 cli`` utilities, e.g. ``ros2 topic``, ``ros2 node``, set the
environment variables above before running the commands.
