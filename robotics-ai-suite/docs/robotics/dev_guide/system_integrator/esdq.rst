.. esdq:

|l_esdq| (|esdq|) for |p_amr|
======================================================================================


Overview
--------


|l_esdq| (|esdq|) for |p_amr| provides customers with the capability to run an
|Intel_Corporation|-provided test suite at the target system, with the goal of enabling
partners to determine their platform's compatibility with the |p_amr|.

The target of this self certification suite is the |p_amr| compute systems.
These platforms are the brain of the Robot Kit. They are responsible to get
input from sensors, analyze them, and give instructions to the motors and wheels
to move the |p_amr|.

.. _esdq-how-it-works:

How It Works
------------

The |p_amr| Test Modules interact with the |esdq| Command Line Interface (CLI) through a common
test module interface (TMI) layer which is part of the |esdq| binary.
|esdq| generates a complete test report in HTML format, along with detailed
logs packaged as one zip file, which you can manually choose to email to:
edge.software.device.qualification@intel.com.
More detailed information is available at `Intel® Edge Software Device Qualification (Intel® ESDQ) Overview
<https://www.intel.com/content/www/us/en/developer/articles/guide/edge-software-device-qualification.html>`__.


.. note::

   Each test and its pass/fail criteria is described below.
   To jump to the installation process, go to :ref:`esdq-install`.

|esdq| for |p_amr| contains the following test modules.

+-------------------------------------------------------------------------------------------------+
| |realsense| Camera                                                                              |
|    This module verifies the capabilities of the |realsense| technology on the target platform.  |
|    For more information, go to the `Intel® RealSense™ website                                   |
|    <https://www.intelrealsense.com/>`__.                                                        |
|                                                                                                 |
|    The tests within this module verify that the following features are installed properly on    |
|    the target platform and that |p_amr| and |realsense| camera are functioning properly.        |
|                                                                                                 |
|    The tests are considered PASS if:                                                            |
|                                                                                                 |
|      -  The |realsense| SDK 2.0 libraries are installed on the target system.                   |
|                                                                                                 |
|      -  A simple C++ file can be compiled using the g++ compiler and the ``-lrealsense2``       |
|         compilation flag.                                                                       |
|                                                                                                 |
|      -  |realsense| Topics are listed and published.                                            |
|                                                                                                 |
|      -  The number of FPS (Frames Per Second) are as expected.                                  |
+-------------------------------------------------------------------------------------------------+
| |intel| |vtune| Profiler                                                                        |
|    This module runs the |intel| |vtune| Profiler on the target system. For more information,    |
|    go to the `Intel® VTune™ Profiler website                                                    |
|    <https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler.html>`__.     |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  |vtune| Profiler runs without errors.                                                   |
|                                                                                                 |
|      -  |vtune| Profiler collects Platform information.                                         |
+-------------------------------------------------------------------------------------------------+
| rviz2 and FastMapping                                                                           |
|   This module runs the FastMapping application (the version of octomap optimized for |intel|    |
|   platforms) on the target system and uses rviz2 to verify that it works as expected.           |
|   For more information, go to the `rviz wiki <http://wiki.ros.org/rviz>`__.                     |
|                                                                                                 |
|   The test is considered PASS if:                                                               |
|                                                                                                 |
|     -  FastMapping is able to create a map out of a pre-recorded |ros| bag.                     |
+-------------------------------------------------------------------------------------------------+
| |l_oneapi|                                                                                      |
|    This module verifies some basic capabilities of |l_oneapi| on the target platform.           |
|    For more information, go to the `Intel® oneAPI Base Toolkit website                          |
|    <https://software.intel.com/content/www/us/en/develop/tools/oneapi.html#gs.cjvm2h>`__.       |
|                                                                                                 |
|    The tests within this module verify that the DPC++ compiler features are functioning         |
|    properly on the target platform.                                                             |
|                                                                                                 |
|    This test is considered PASS if:                                                             |
|                                                                                                 |
|      -  A simple C++ file can be compiled using the DPC++ compiled and it runs as expected.     |
+-------------------------------------------------------------------------------------------------+
| |openvino| Toolkit                                                                              |
|    This module verifies two core features of the |openvino| Toolkit:                            |
|                                                                                                 |
|      -  |openvino| model optimizer                                                              |
|                                                                                                 |
|      -  Object detection using TensorFlow model                                                 |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  The |openvino| model optimizer is capable to transform a TensorFlow model to an         |
|         Intermediate Representation (IR) of the network, which can be inferred with the         |
|         Inference Engine.                                                                       |
+-------------------------------------------------------------------------------------------------+
| |openvino| Query for inferencing devices                                                        |
|    This module executes the                                                                     |
|    `Hello Query Device                                                                          |
|    <https://docs.openvino.ai/2024/learn-openvino/openvino-samples/hello-query-device.html>`__   |
|    C++ sample application of the |openvino| toolkit. This application identifies all            |
|    available devices that can be used for inferencing.                                          |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  The |openvino| Hello Query Device sample application can identify the inferencing       |
|         devices ``CPU`` and ``GPU``.                                                            |
|                                                                                                 |
|      -  On |core| Ultra Processors, in addition the ``NPU`` must be be identified as an         |
|         inferencing device.                                                                     |
+-------------------------------------------------------------------------------------------------+
| |gstreamer| Video                                                                               |
|    This module verifies if a |gstreamer| Video Pipeline using |gstreamer| Plugins runs on the   |
|    target system.                                                                               |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  The Video Pipeline was opened on the host without errors.                               |
+-------------------------------------------------------------------------------------------------+
| |gstreamer| Audio                                                                               |
|    This module verifies if a |gstreamer| Audio Pipeline using |gstreamer| Plugins runs on the   |
|    target system.                                                                               |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  The Audio Pipeline was opened on the host without errors.                               |
+-------------------------------------------------------------------------------------------------+
| |gstreamer| Autovideosink Plugin - Display                                                      |
|    This module verifies if a stream from a camera compatible with libv4l2 can be opened and     |
|    displayed using |gstreamer|.                                                                 |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  No Error messages are displayed while running the gst-launch command.                   |
|                                                                                                 |
|    This test may Fail, or it may be skipped if the target system does not have a Web Camera     |
|    connected.                                                                                   |
+-------------------------------------------------------------------------------------------------+
| ADBSCAN                                                                                         |
|    This module verifies if the ADBSCAN algorithm works on the target system.                    |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  The ADBSCAN algorithm works on the target system.                                       |
+-------------------------------------------------------------------------------------------------+
| Collaborative Visual SLAM                                                                       |
|    This module verifies if the collaborative visual SLAM algorithm works on the target system.  |
|                                                                                                 |
|    The test is considered PASS if:                                                              |
|                                                                                                 |
|      -  The collaborative visual SLAM algorithm works on the target system.                     |
+-------------------------------------------------------------------------------------------------+

Get Started
-----------

This tutorial takes you through the installation and execution of the |esdq| CLI tool.
Configure your target system to satisfy the necessary :ref:`esdq-prerequisites`
before you proceed with the :ref:`esdq-install`.
Execute your self-certification process by selecting from the three available
certification types:

-  :ref:`esdq_compute` for certifying |intel|-based compute systems with
   the |p_amr| software

-  :ref:`esdq_sensor_rgb` for certifying RGB cameras with the |p_amr|
   software

-  :ref:`esdq_sensor_depth` for certifying depth cameras with the |p_amr|
   software

Refer to :ref:`esdq-how-it-works` for more detailed information about the test
modules.

.. _esdq-prerequisites:

Prerequisites
-------------

Satisfy the |esdq| prerequisites by:

- Installing |openvino| Development Tools and specifying ``tensorflow`` as the extras parameter
  of the described "Step 4. Install the Package" `instructions
  <https://docs.openvino.ai/2024/documentation/legacy-features/install-dev-tools.html#step-4-install-the-package>`__:

  .. code-block:: bash

     pip install openvino-dev[tensorflow]

- Installing the ``intel-basekit`` |deb_pack| by following the |l_oneapi|
  Installation Guide for |Linux| OS `instructions
  <https://www.intel.com/content/www/us/en/docs/oneapi/installation-guide-linux/2023-2/apt.html>`__.

- Installing |gstreamer| by following the "Install |GStreamer| on |Ubuntu_OS| or |Debian_OS|"
  `instructions
  <https://gstreamer.freedesktop.org/documentation/installing/on-linux.html?gi-language=c#install-gstreamer-on-ubuntu-or-debian>`__.

- Installing the pre-built |realsense| SDK 2.0 packages ``librealsense2-utils``,
  ``librealsense2-dev`` and ``librealsense2-dbg`` by following the "Installing
  the packages" `instructions
  <https://github.com/IntelRealSense/librealsense/blob/master/doc/distribution_linux.md#installing-the-packages>`__.

- Configuring your |vtune| installation as described in the
  "Additional System setup for CPU and GPU profiling" section of
  :doc:`benchmark_profiling/vtune-profiler`.

- Installing the |openvino| Runtime by executing these steps:

  #. Add the |openvino| APT package sources as described in section "|openvino| Installation Steps"
     on page :doc:`../../gsg_robot/install-openvino`.
  #. Make sure that your file ``/etc/apt/preferences.d/intel-openvino``
     pins the |openvino| version of all components to ``2024.2.0*`` or above.
     Consider that earlier |openvino| versions do not support the NPU of
     |core| Ultra Processors.
  #. Install the |openvino| Runtime by using:

     .. code-block:: bash

        sudo apt-get install openvino

  Additional information can be found in the
  `OpenVINO™ documentation
  <https://docs.openvino.ai/2024/get-started/install-openvino/install-openvino-apt.html>`__.

- Installing the |intel| NPU Driver as described on page
  :doc:`../../gsg_robot/install-npu-driver`. Don't execute this step if
  your system does not have an |core| Ultra Processor.

.. note::

   Make sure that `Git` is installed on your target system.

.. _esdq-install:

Download and Install |esdq| for |p_amr|
---------------------------------------------------------------

Complete the following two installation steps in order to properly configure
your test setup:

#. :ref:`esdq-install-cli`

#. :ref:`esdq-install-module`

.. _esdq-install-cli:

Download and Install |esdq| CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Download the |esdq| CLI to your device from here:
:download:`edge-software-device-qualification-11.0.0.zip <https://amrdocs.intel.com/downloads/edge-software-device-qualification-11.0.0.zip>`

Set the ``ESDQ_INSTALLATION`` variable to point to the desired installation
location. For example, if you want to install the the |esdq| CLI under
the ``~/esdq`` directory, just set the this variable as follows:

.. code-block:: bash

   export ESDQ_INSTALLATION=~/esdq
   mkdir $ESDQ_INSTALLATION

Directly from the download directory, unzip the downloaded file into the
installation location.

.. code-block:: bash

   unzip edge-software-device-qualification-11.0.0.zip -d $ESDQ_INSTALLATION

Set the convenient ``ROBOTICS_SDK`` variable that is going to be used
in the next installation steps.

.. code-block:: bash

   export ROBOTICS_SDK=$ESDQ_INSTALLATION/edge-software-device-qualification-11.0.0/

Install the |esdq| CLI executing the following commands:

.. code-block:: bash

   cd $ROBOTICS_SDK
   ./setup.sh -i
   export PATH=$PATH:$HOME/.local/bin

Check the successful installation of the |esdq| CLI verifying that the execution
of the following command prints ``Version: 11.0.0`` on the terminal:

.. code-block:: bash

   esdq --version

.. _esdq-install-module:

Download and Install the Test Modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To download and install the |lp_amr| test modules on your target device follow the
steps below:

#. Install the ``ros-humble-amr-esdq`` |deb_pack| from
   |intel| |p_amr| APT repository.

   .. code-block:: bash

      sudo apt update
      sudo apt install ros-humble-amr-esdq

#. The tests are conducted from the directory pointed by the previously set
   ``ROBOTICS_SDK`` variable. Copy the installed test suite into the directory.

   .. code-block:: bash

      cp -r /opt/ros/humble/share/amr-esdq/AMR_Test_Module/ $ROBOTICS_SDK/modules/

#. Verify the appropriate permissions for the test modules directory by executing
   the following command:

   .. code-block:: bash

      cd $ROBOTICS_SDK
      chmod -R +xw  modules/AMR_Test_Module

#. Check that the |lp_amr| test module is correctly installed by verifying that
   the output of the following command lists the ``Robotics_SDK`` module.

   .. code-block:: bash

      esdq module list

#. Download the necessary assets required by the test suite.

   .. code-block:: bash

      esdq --verbose module run Robotics_SDK --arg download

.. _esdq_compute:

Run the Self-Certification Application for Compute Systems
----------------------------------------------------------

#. Use the ``groups`` command to verify whether the current user belongs to
   the ``render``, ``video``, and ``dialout`` groups.
   If the user does not belong to these groups, add the group membership
   by means of:

   .. code-block:: bash

      sudo usermod -a -G render,video,dialout $USER

   Log out and log in again.

#. If you have just installed the ``ros-humble-amr-esdq`` |deb_pack| as
   described in the :ref:`esdq-install` section, reboot your system.

   Otherwise, there is a possibility that the tests that depend on the
   :doc:`../../dev_guide/tutorials_amr/perception/orb-extractor/index`
   encounter issues accessing the GPU.


#. Make sure that the environment variable ``ROBOTICS_SDK`` is initialized
   as shown in :ref:`esdq-install` and change the working directory:

   .. code-block:: bash

      echo $ROBOTICS_SDK
      cd $ROBOTICS_SDK


#. If your system uses a |Linux| Kernel 6.7.5 or later, read the section
   :ref:`troubleshooting-gpu-not-detected`.
   If your system is impacted by this issue, export the following debug
   variables as a workaround:

   .. code-block:: bash

      export NEOReadDebugKeys=1
      export OverrideGpuAddressSpace=48

#. Run the |esdq| test, and generate the report:

   .. code-block:: bash

      export ROS_DOMAIN_ID=19
      esdq --verbose module run Robotics_SDK

#. Visualize the report by opening the ``reports/report.html`` file in your browser.

   Expected output (These results are for illustration purposes only.)


   .. image:: ../../images/esdq_execution_summary.png

   .. image:: ../../images/esdq_test_module.png

   .. image:: ../../images/esdq_test_results.png

   .. note::

      All the tests are expected to pass.
      The |vtune| test failure and the |realsense| test skip above
      are shown for demonstration purposes only. For example, the execution of
      the |realsense| test is skipped if no |realsense| camera is connected to
      the target system.

      If individual test cases do not pass, you can check the detailed
      log files in folder ``$ROBOTICS_SDK/modules/AMR_Test_Module/output/``.


.. _esdq_sensor_rgb:

Run the Self-Certification Application for RGB Cameras
----------------------------------------------------------

This self-certification test expects the camera stream to be on the
``/camera/color/image_raw`` topic. This topic must be visible in rviz2 using
the `camera_color_frame` fixed frame. If your camera |ros| node does not
stream to that topic by default, use |ros| remapping to publish to that
topic.

.. note::

   The following steps use the |realsense| |ros| node as an example. You must
   change the node to your actual camera |ros| node.

You can check your current configuration by:

#. Running the RGB camera node in a |ros| environment after setting the
   ``ROS_DOMAIN_ID``.

   .. code-block:: bash

      source /opt/ros/humble/setup.bash
      # set a unique id here that is used in all terminals
      export ROS_DOMAIN_ID=19
      ros2 launch realsense2_camera rs_launch.py camera_namespace:=/ &

#. Verifying the presence of the topic in the topic list.

   .. code-block:: bash

      ros2 topic list

#. Once your configuration is set, you can proceed to run the |esdq| test
   and generate the report.

   .. code-block:: bash

      cd $ROBOTICS_SDK
      export ROS_DOMAIN_ID=19
      esdq --verbose module run Robotics_SDK --arg sensors_rgb


.. _esdq_sensor_depth:

Run the Self-Certification Application for Depth Cameras
----------------------------------------------------------

This self-certification test expects the camera stream to be on the
``/camera/depth/color/points`` and on the ``/camera/depth/image_rect_raw`` topics.
These topics must be visible in rviz2 using the `camera_link` fixed frame.
If your camera |ros| node does not stream to that topic by default, use
|ros| remapping to publish to that topic.

.. note::

   The following steps use the |realsense| |ros| node as an example. You must
   change the node to your actual camera |ros| node.

You can check your current configuration by:

#. Running the depth camera node in a |ros| environment after setting the ``ROS_DOMAIN_ID``.

   .. code-block:: bash

      source /opt/ros/humble/setup.bash
      # set a unique id here that is used in all terminals
      export ROS_DOMAIN_ID=19
      ros2 launch realsense2_camera rs_launch.py pointcloud.enable:=true camera_namespace:=/ &

#. Verifying the presence of the topic in the topic list.

   .. code-block:: bash

      ros2 topic list

#. Once your configuration is set, you can proceed to run the |esdq| test
   and generate the report.

   .. code-block:: bash

      cd $ROBOTICS_SDK
      export ROS_DOMAIN_ID=19
      esdq --verbose module run Robotics_SDK --arg sensors_depth


Send Results to |Intel_Corporation|
-----------------------------------

Once the automated and manual tests are executed successfully, you can
submit your test results and get your devices listed on the `Intel® Edge
Software Recommended Hardware
<https://www.intel.com/content/www/us/en/developer/topic-technology/edge-5g/edge-solutions/hardware.html>`__
site.

Send the zip file that is created after running |esdq| tests to:
edge.software.device.qualification@intel.com.

For example, after one of our local runs the following files were generated in the
``$ROBOTICS_SDK/reports/`` directory: ``report.html`` and ``report.zip``.

Troubleshooting
----------------

For issues, go to: :doc:`../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.

Support Forum
-------------

If you're unable to resolve your issues, contact the `Support Forum.
<https://software.intel.com/en-us/forums/intel-edge-software-recipes>`__
