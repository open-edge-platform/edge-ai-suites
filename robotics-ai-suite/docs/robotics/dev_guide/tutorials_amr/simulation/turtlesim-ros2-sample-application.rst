.. turtlesim-ros2-sample-application:

Turtlesim |ros| Sample Application
==============================================================


This tutorial describes how to:

- Launch ROS nodes and graphic application for turtlesim.

- List ROS topics.

- Launch rqt graphic application so that the turtle can be controlled.

- Launch rviz graphic application to view ROS topics.


Run the Turtlesim |ros| Sample application
--------------------------------------------------------------


#. To download and install the Turtlesim |ros| sample application run the command below:

   .. code-block::


      sudo apt-get install ros-humble-turtlesim-tutorial-demo

#. Set up your |ros| environment

   .. code-block::


      source /opt/ros/humble/setup.bash

#. Run the Turtlesim |ros| sample application:

   .. code-block::


      ros2 launch turtlesim_tutorial turtlesim_tutorial.launch.py

#. In the rqt application, navigate to **Plugins** > **Services** > **Service Caller**. To move 'turtle1',
   choose /turtle1/teleport_absolute from the service dropdown list.
   Ensure to update the x and y values from their original settings.
   Press the 'Call' button to execute the teleportation.
   To close the Service Caller window, click the 'X' button.

   Expected Output: The Turtle has been relocated to the coordinates entered in the rqt application.

   .. image:: ../../../images/23D9D8D8-AFB8-43EF-98A3-995EE956EF5B-low.png

#. In the rviz application, navigate to **Add** > **By topic**. Check the option 'Show Unvisualizable Topics' to view hidden topics.
   You will now be able to view the hidden topics from 'turtlesim'. To close the window, click the 'Cancel' button.

#. To close this tutorial, do the following:

   -  Type ``Ctrl-c`` in the terminal where you executed the command for the tutorial.
