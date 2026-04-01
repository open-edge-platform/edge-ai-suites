
.. _api_development:

API Development
###################

To utilize the RVC API, follow the steps outlined below:

Start by creating a ROS package:

.. code-block:: bash

    ros2 pkg create --build-type ament_cmake <package_name>

Next, add the following line to your package.xml:

.. code-block:: xml

      <depend>rvc_messages</depend>

Lastly, add the following lines to the corresponding sections in your CmakeLists.txt:

.. code-block:: cmake

   find_package(rvc_messages REQUIRED)
   ament_target_dependencies(${PROJECT_NAME_PLUGIN}
   [...]
   rvc_messages
   )

As a rule of thumb, we suggest using `sensor data <https://docs.ros.org/en/rolling/Concepts/Intermediate/About-Quality-of-Service-Settings.html>`_ as the Quality of Service when creating subscriptions and/or publishers.

Typically, the publisher, usually part of the RVC Vision component, will publish the RVC API message upon detection.

.. code-block:: c++

    m_pub_poses = this->create_publisher<rvc_messages::msg::PoseStampedList>("object_poses", qos);
    [...]
    rvc_messages::msg::PoseStampedList outMsg;
    rvc_messages::msg::PoseStamped poseStamped;
    poseStamped.pose_stamped.header.stamp = now();
    [...]
    outMsg.poses.push_back(poseStamped);
    m_pub_poses->publish(outMsg);


