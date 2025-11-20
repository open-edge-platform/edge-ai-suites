.. segmentation-realsense-tutorial:

OpenVINO™ Tutorial with Segmentation
=======================================

This tutorial serves as an example for understanding the utilization of the ROS 2 OpenVINO™ node.
It outlines the steps for installing and executing the semantic segmentation model using the ROS 2 OpenVINO™ toolkit.
This tutorial uses the Intel® RealSense™ camera image as input and performs inference on CPU, GPU devices.

Prerequisites
^^^^^^^^^^^^^

Complete the :doc:`../../../../gsg_robot/index` before continuing.

Install OpenVINO™ tutorial packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   sudo apt install ros-humble-segmentation-realsense-tutorial

Run Demo with Intel® RealSense™ Camera Topic Input
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run one of the following commands to launch the segmentation tutorial with a specific inference engine:

*  GPU inference engine

   .. code-block::

      ros2 launch segmentation_realsense_tutorial openvino_segmentation.launch.py device:=GPU

*  CPU inference engine

   .. code-block::

      ros2 launch segmentation_realsense_tutorial openvino_segmentation.launch.py device:=CPU

.. note::

   If no device is specified, the GPU is selected by default as inference engine.

Once the tutorial is started, the ``deeplabv3`` model is downloaded, converted into IR files,
and the inference process begins, utilizing the input from the Intel® RealSense™ camera.


To exit the application, press ``Ctrl-c`` in the terminal where the launch script was executed.

Troubleshooting
---------------


For general robot issues, go to: :doc:`../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.
