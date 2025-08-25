Tools
------


|ros| Tools
++++++++++++


The |lp_amr| is validated using |ros| tools as it is not compatible with ROS 1
components. To facilitate interaction, a ROS 1 bridge is included, enabling |p_amr| components to
interface with ROS 1 components.


-  From the hardware perspective of the supported platforms, there are no known
   limitations for ROS 1 components.

-  For information on porting ROS 1 applications to |ros|, refer to the  `How to Guide
   <https://docs.ros.org/en/rolling/Contributing/Migration-Guide.html>`__.


|lp_amr| includes:


-  `rqt <http://wiki.ros.org/rqt>`__, a software framework of |ros| that
   implements the various GUI tools in the form of plugins.

-  `rviz2 <https://github.com/ros2/rviz>`__, a tool used to visualize |ros|
   topics.

-  `colcon <https://colcon.readthedocs.io/>`__ (collective construction), a
   command line tool to improve the workflow of building, testing, and using
   multiple software packages (It automates the process, handles the ordering,
   and sets up the environment to use the packages.)


Simulation Tools
+++++++++++++++++


-  The `Gazebo\* robot simulator
   <https://classic.gazebosim.org/tutorials/?tut=ros_wrapper_versions>`__,
   making it possible to rapidly test algorithms, design robots, perform
   regression testing, and train AI systems using realistic scenarios. Gazebo
   offers the ability to simulate populations of robots accurately and
   efficiently in complex indoor and outdoor environments.

-  An `industrial simulation room model for Gazebo\*
   <https://classic.gazebosim.org/ariac>`__, the Open Source Robotics Foundation
   (OSRF) Gazebo Environment for Agile Robotics (GEAR) workcell that was used
   for the ARIAC competition in 2018.

-  A Pick and place simulation demo to showcase the interaction of a conveyor belt, a TurtleBot3 Waffle Autonomous Mobile Robot (AMR), and two UR5 robotic arms (ARM) in a simulated environment.  

-  Wandering application in Gazebo simulation to showcase autonomous mapping of a gazebo world using TurtleBot3 Waffle robot. 

Other Tools
+++++++++++++


-  **Intel® oneAPI Base Toolkit** encompasses essential components such as the DPC++ compiler, compatibility tool and a suite of
   debugging and profiling tools, like the VTune™ Profiler (formerly known
   as Intel System Studio).

-  **Intel® Distribution of OpenVINO™ toolkit**, inclusive of the Model Optimization Tool.

-  **Intel® ESDQ**, is a self-certification test suite to enable partners to determine their 
   platform's compatibility with the |p_amr|.

-  **AWS* RoboMaker**, a cloud-based simulation service, empowers robotics
   developers to run, scale, and automate simulation seamlessly without the need to manage any
   infrastructure.

-  **Foxglove Studio**, interactive visualizations to analyze live connections and
   pre-recorded data.
