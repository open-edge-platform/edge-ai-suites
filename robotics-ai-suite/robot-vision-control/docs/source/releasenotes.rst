.. Table of contents contained in `index.rst`

.. _releasenotes:

Release Notes
###################################

Click each tab to learn about the new and updated features in each release of Intel® |rvc_full|.

.. tabs::

   .. group-tab:: |rvc| v2.1

      |rvc| v2.1 release includes bug and security updates as well as adds two new components: Intel Lab's Dobby Path Planner, an adaptive path planner that improves robot arm performance in complex environments; and Intel Lab’s Histodepth Pointcloud Segmentation algorithm in a Virtual Fence application. 
      
      - **Intel Lab's Dobby Path Planner**: This new planner, available as an option in RVC's dynamic motion use case, enables fast collision checking, a new geometric path planner based on rapidly exploring random trees, new trajectory generation methods for user-specific optimization criteria, and a novel cartesian trajectory generation algorithm that allows tracking time-dependent trajectories in cartesian space enabling self and obstacle collision avoided while producing dynamically feasible trajectories.
      - **Intel Lab's Histodepth Pointcloud Segmentation Virtual Fence**: Now part of the RVC package, this virtual fence application running on ROS uses depth information from an Intel RealSense camera to create dynamic and static scene segmentation maps to enable live robotic virtual fencing and safety bounding. The use of this segmentation algorithm enables a drop-in approach to virtual fencing, requiring no training or learning before deployment.

      **Features**

      - New dynamic path planning algorithm available.
      - New dynamic virtual fencing algorithm available.

      **Known Limitations and Issues**

   .. group-tab:: |rvc| v2.0

      |rvc| v2.0 provides a SW framework to control a robot based on vision based object detection.
      It's a collection of SW components that can be deployed provided a debian packages.
      But it is expected to be customized, hardened, optimized and extended by customers before it’s used as a final product.

      |rvc| focuses on demonstrating consolidation of the following functionalities:

      - Camera input
      - Vision based object classification and 3D pose detection.
      - Trajectory calculation to detected object pose.
      - Robot control

      **Features**

      - Defined API between vision and control.
      - 3D detection and 3D pose detection components.
      - 2.5D detection and pose detection components.
      - Control of ROS2 supporting Robots.
      - Control of ROS2 not supported robots (example implementation for UR5).
      - Simple static and dynamic use case example.

      **Known Limitations and Issues**

      **Debian packages:**

      .. list-table::
         :widths: 50 70 70
         :header-rows: 1

         * - Package
           - Deb Package
           - Description
         * - gui-settings
           - ``ros-humble-gui-settings_2.0.0jammy_amd64.deb``
           - Custom message for GUI to RVC communication Package.
         * - moveit2-servo-motion-controller
           - ``ros-humble-moveit2-servo-motion-controller_1.0.0jammy_amd64.deb``
           - RVC Motion controller interface-based plugin implemented using moveit2 servo.
         * - non-oriented-grasp
           - ``ros-humble-non-oriented-grasp_2.0.0jammy_amd64.deb``
           - Non oriented grasp plugin.
         * - openvino-inference-plugin
           - ``ros-humble-openvino-inference-plugin_2.0.0jammy_amd64.deb``
           - RVC AI interface-based Plugin implementing yolo V5, v6 and V8 using openvino inferencing.
         * - oriented-grasp
           - ``ros-humble-oriented-grasp_2.0.0jammy_amd64.deb``
           - Non oriented grasp plugin.
         * - robotiq-controllers
           - ``ros-humble-robotiq-controllers_2.0.0jammy_amd64.deb``
           - Provides controllers for robotiq 2f gripper.
         * - robotiq-driver-plugin
           - ``ros-humble-robotiq-driver-plugin_2.0.0jammy_amd64.deb``
           - Robotiq 2f driver.
         * - rvc-ai-interface
           - ``ros-humble-rvc-ai-interface_2.0.0jammy_amd64.deb``
           - Interface every 2.5D AI plugin shall inmplement.
         * - rvc-dynamic-motion-controller-use-case
           - ``ros-humble-rvc-dynamic-motion-controller-use-case_2.0.0jammy_amd64.deb``
           - Main package for RVC motion controller.
         * - rvc-grasp-interface
           - ``ros-humble-rvc-grasp-interface_2.0.0jammy_amd64.deb``
           - Pluginlib interface that a pose to grasp plugin has to implement.
         * - rvc-messages
           - ``ros-humble-rvc-messages_2.0.0jammy_amd64.deb``
           - RVC vision interface messages.
         * - rvc-motion-controller-interface
           - ``ros-humble-rvc-motion-controller-interface_2.0.0jammy_amd64.deb``
           - Interface defining how motion controller plugins shall be implemented.
         * - rvc-object-detection-engine
           - ``ros-humble-rvc-object-detection-engine_2.0.0jammy_amd64.deb``
           - AI inference pipeling Stage 1 object detection engine, plugin based to allow different AI models, and devices.
         * - rvc-packages-all
           - ``ros-humble-rvc-packages-all_2.0.0jammy_amd64.deb``
           - Metapackage aggreating all RVC packages.
         * - rvc-panel-rviz2-plugin
           - ``ros-humble-rvc-panel-rviz2-plugin_2.0.0jammy_amd64.deb``
           - RVC controls for RViz.
         * - rvc-pose-detector
           - ``ros-humble-rvc-pose-detector_2.0.0jammy_amd64.deb``
           - AI pose alignment stage Package.
         * - rvc-profiler
           - ``ros-humble-rvc-profiler_2.0.0jammy_amd64.deb``
           - Node to gather various statistics of RVC.
         * - rvc-rotated-object-detection
           - ``ros-humble-rvc-rotated-object-detection_2.0.0jammy_amd64.deb``
           - Rotated object detection using ORB features.
         * - rvc-static-motion-controller-use-case
           - ``ros-humble-rvc-static-motion-controller-use-case_2.0.0jammy_amd64.deb``
           - Main package for RVC motion controller.
         * - rvc-vision-main
           - ``ros-humble-rvc-vision-main_2.0.0jammy_amd64.deb``
           - Start up and configuration files for the whole vision component.
         * - rvc-vision-messages
           - ``ros-humble-rvc-vision-messages_2.0.0jammy_amd64.deb``
           - Custom message between AI and motion controller.
         * - state-machine-msgs
           - ``ros-humble-state-machine-msgs_2.0.0jammy_amd64.deb``
           - Custom message for state machines communication Package.
         * - trac-ik-kinematics-plugin
           - ``ros-humble-trac-ik-kinematics-plugin_1.6.6jammy_amd64.deb``
           - A MoveIt! Kinematics plugin using TRAC-IK.
         * - trac-ik-lib
           - ``ros-humble-trac-ik-lib_0.1.0jammy_amd64.deb``
           - TRAC-IK is a faster, significantly more reliable drop-in replacement for KDL's pseudoinverse Jacobian solver.
         * - ur-pendant-motion-controller
           - ``ros-humble-ur-pendant-motion-controller_1.0.0jammy_amd64.deb``
           - Direct Universal Robot pendant controller.

   .. group-tab:: |rvc| v1.0

      Initial release of |rvc_full| (|rvc|).
      |rvc| allows closed loop automatic object recognition and robot manipulation of a set of moving objects.

      **Features**

      - Six Degree of Freedom (6DoF) real-time object detection
      - Manipulator dynamic tracking, that is, robot adjusts trajectory towards target in real-time

      **Known Limitations and Issues**

      - The object set must be known prior, that is, the objects need to be present on file system in the pointcloud format, matching the real objects
      - Camera position must be accurate by either adjusting the camera in a particular position or changing the position in a configuration file
      - Only the Universal Robots™ family has been tested (more specifically, UR5e), the Robotiq 2F-85 Gripper and D415 Intel® RealSense™ Camera.
      - Only one object can be placed under the camera. Multiple objects could work, however there are known issues. For this release, make sure that there is only one object under the camera or none.

.. Table of contents contained in `index.rst`
