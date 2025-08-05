.. launch-wandering-application-gazebo-sim-waffle:

Wandering Application in a Waffle Gazebo\* Simulation
=======================================================


This tutorial shows a |tb3| Waffle performing autonomous mapping of a |tb3| world in Gazebo simulation.
For more information about |tb3| Waffle, see `this <https://emanual.robotis.com/docs/en/platform/turtlebot3/simulation/#gazebo-simulation>`__.

Run the Sample Application
--------------------------


#. If your system has an |intel| GPU, follow the steps in the |GSG Robot| to
   enable the GPU for simulation. This step improves Gazebo* simulation
   performance.


#. Install the Wandering Gazebo tutorial:


   .. code-block:: bash

      sudo apt-get install ros-humble-wandering-gazebo-tutorial


#. Execute the command below to start the tutorial:


   .. code-block:: bash


      ros2 launch wandering_gazebo_tutorial wandering_gazebo.launch.py


   **Expected output:**

   Gazebo* client, rviz2 and RTAB-Map applications start and the robot
   starts wandering inside the simulation. See the simulation
   snapshot:

   .. image:: ../../../images/gazebo_waffle.png

   Rviz2 shows the mapped area and the position of the robot:

   .. image:: ../../../images/wandering-gazebo-rviz2.png

   To enhance performance, set the real-time update to 0 by following
   the steps below:

   a. In Gazebo*'s left panel, go to the **World** Tab, and click
      **Physics**.

   #. Change the real time update rate to 0.


#. To conclude, use ``Ctrl-c`` in the terminal where you are executing
   the command.


Troubleshooting
---------------

For general robot issues, go to: :doc:`../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.
