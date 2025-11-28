Autonomous Mobile Robot Middleware
------------------------------------


-  `Intel® Distribution of OpenVINO™ toolkit
   <https://www.intel.com/content/www/us/en/developer/tools/openvino-toolkit/overview.html>`__
   is a comprehensive toolkit for rapidly developing applications and
   solutions across a range of tasks. This includes emulation of human vision,
   automatic speech recognition, natural language processing, recommendation
   systems, and more. Built on latest generations of artificial neural
   networks, including Convolutional Neural Networks (CNNs), recurrent and
   attention-based networks, the toolkit extends computer vision and non-vision
   workloads across Intel® hardware, optimizing performance. It accelerates
   applications with high-performance AI and deep learning inference, deployed
   from edge to the cloud.

-  `Intel® oneAPI Base Toolkit
   <https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit.html>`__,
   is capable of executing sample applications in the toolkit. This core set of tools and libraries is designed for
   developing high-performance, data-centric applications across diverse architectures. It features an industry-leading
   C++ compiler and the Data Parallel C++ (DPC++) language, an evolution of C++
   for heterogeneous computing. For Intel® oneAPI Base Toolkit training, refer to:

   -  `Intel® DPC++ Compatibility Tool Self-Guided Jupyter Notebook Tutorial
      <https://www.intel.com/content/www/us/en/developer/articles/training/intel-dpcpp-compatibility-tool-training.html>`__

-  The Intel® RealSense™ ROS 2 Wrapper node is utilized for Intel® RealSense™ cameras within ROS 2.

-  The `Intel® RealSense™ SDK <https://dev.intelrealsense.com/docs/ros-wrapper>`__ is
   used to implement software for Intel® RealSense™ cameras.

-  The ROS 2 OpenVINO™ Toolkit provides a ROS 2 adapted runtime framework of
   neural networks, enabling rapid deployment of applications and solutions for vision
   inference.

-  AAEON* ROS 2 interface, the ROS 2 driver node for AAEON Autonomous Mobile Robot\s.

-  Slamtec* RPLIDAR ROS 2 Wrapper node for using RPLIDAR LIDAR sensors with
   ROS 2.

-  SICK Safetyscanners ROS 2 Driver reads the raw data from the SICK
   Safety Scanners and publishes the data as a laser_scan msg.

-  ROS 2 ros1_bridge, facilitates a network bridge for exchanging
   messages between ROS1 and ROS 2. This allows users to evaluate the Autonomous Mobile Robot on
   Autonomous Mobile Robot\s or with sensors for which only ROS1 driver nodes exist.

-  ROS 2, Robot Operating System (ROS) is a collection of open-source software
   libraries and tools designed for building robot applications. ROS 2 depends on other middleware, like the Object
   Management Group (OMG) DDS connectivity framework which utilizes a publish-subscribe pattern (The
   standard ROS 2 distribution includes eProsima Fast DDS implementation.)

-  `OpenCV (Open Source Computer Vision Library) <https://opencv.org>`__ is an
   open-source library that includes several hundred computer vision algorithms.

-  `GStreamer_Framework <https://gstreamer.freedesktop.org/documentation>`__
   includes support for libv4l2 video sources, GStreamer "good" plugins for
   video and  audio, and a GStreamer plugin for display to show a video
   stream in a window.

-  Teleop Twist Joy is a generic facility for teleoperating twist-based ROS 2
   robots with a standard joystick. It converts joy messages to velocity
   commands. This node does not include rate limiting or auto-repeat functionality. It
   is recommended to leverage the features integrated into ROS 2 Driver
   for a Generic Joystick.

-  Teleop Twist Keyboard provides a generic keyboard teleoperation solution for ROS 2.

-  The Twist Multiplexer is essential in scenarios where multiple sources move a robot using
   a geometry_msgs::Twist message. It plays important role in multiplexing all input
   sources into a single source that goes to the Autonomous Mobile Robot control node.

-  The ROS 2 Driver for Generic Joysticks.
