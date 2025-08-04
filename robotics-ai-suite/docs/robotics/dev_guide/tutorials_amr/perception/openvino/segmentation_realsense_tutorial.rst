.. segmentation-realsense-tutorial:

|openvino| Tutorial with Segmentation
=======================================

This tutorial serves as an example for understanding the utilization of the |ros| |openvino| node.
It outlines the steps for installing and executing the semantic segmentation model using the |ros| |openvino| toolkit.
This tutorial uses the |realsense| camera image as input and performs inference on CPU, GPU devices.


Install |openvino| tutorial packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   sudo apt install ros-humble-segmentation-realsense-tutorial

Run Demo with |realsense| Topic Input
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
and the inference process begins, utilizing the input from the |realsense| camera.


To exit the application, press ``Ctrl-c`` in the terminal where the launch script was executed.

Troubleshooting
---------------


For general robot issues, go to: :doc:`../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.