.. |troubleshooting| image:: ../../images/icons/Magnifying_Glass_Robot.png
   :width: 70
   :align: bottom

.. robot-tutorials-troubleshooting:

Troubleshooting for |p_amr| Tutorials |troubleshooting|
=======================================================

.. _shared_robot-tutorials-troubleshooting_start:

Use ``ROS_DOMAIN_ID`` to Avoid Interference in ROS Messages
------------------------------------------------------------

A typical method to demonstrate a use case requires you to start several
|ros| nodes and exchange |ros| messages between the |ros| nodes.

However, interference from unrelated nodes -- whether on the same host machine
or within the local network -- can disrupt the process. Debugging and
resolving such interference can be challenging in this scenario.

|ros| uses the ``ROS_DOMAIN_ID`` environment variable to isolate several
use cases from each other. For this reason, you should set this variable
to a certain number before you execute a tutorial:

.. code-block:: bash

   export ROS_DOMAIN_ID=<value>

The ``ROS_DOMAIN_ID`` should be an integer between 0 and 101 and it should
be the same for all the nodes launched for a particular use case. If you run only
one use case at a time, you can set this variable in your ``.bashrc`` file,
as described in the :ref:`prepare-ros-environment` section.


.. _shared_robot-tutorials-troubleshooting_aaeon-motor-control-board:

Troubleshooting AAEON Motor Control Board Issues
------------------------------------------------

Several tutorials apply an |up_xtreme| to demonstrate how the |lp_amr|
can interact with a physical robot. The |up_xtreme| includes a motor control
board, which implements the motor drivers and the USB interface towards the compute
board. To support this motor control board, the |lp_amr| provides the |deb_pack|
``ros-humble-aaeon-ros2-amr-interface``, which is based on the GitHub project
`AAEONAEU-SW/ros2_amr_interface
<https://github.com/AAEONAEU-SW/ros2_amr_interface>`_
with some adaptations for |ros| Humble.

The following subsections provide solutions to fix potential issues with
the USB interface of the |up_xtreme|.


Add the current user to the ``dialout`` group
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To control the |up_xtreme| via the USB interface, the current user must be a
member of the ``dialout`` group. Use the ``groups`` command to verify that the
current user belongs to the ``dialout`` group. If the user does not belong
to this group, add the group membership by means of:

.. code-block:: bash

   sudo usermod -a -G dialout $USER


Solve conflicts with the BRLTTY daemon
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

BRLTTY is a background process that operates Braille displays, a tool for individuals 
who are blind. There is a possibility that BRLTTY may block the USB interface
utilized by the AAEON motor control board. To identify such a conflict,
execute the following command:

.. code-block:: bash

   sudo dmesg -w

Connect the AAEON motor control board to one of the USB ports of the
compute board. Analyze the output of the ``dmesg`` command and search for any
messages that contain ``BRLTTY`` or ``brltty``. In the following example, the
lines with the time stamps ``7768.502123`` and ``7768.618382`` indicate
that there is a conflict between the BRLTTY daemon and the ch341 driver.

.. code-block:: text

   [ 7750.500707] usb 3-4: USB disconnect, device number 11
   [ 7767.801366] usb 3-4: New full-speed USB device number 12 using xhci_hcd
   [ 7767.951513] usb 3-4: New USB device found, idVendor=1a86, idProduct=7523, bcdDevice= 2.64
   [ 7767.951532] usb 3-4: New USB device strings: Mfr=0, Product=2, SerialNumber=0
   [ 7767.951537] usb 3-4: Product: USB Serial
   [ 7767.953988] ch341 3-4:1.0: ch341-uart converter detected
   [ 7767.954920] usb 3-4: ch341-uart converter now attached to ttyUSB0
   [ 7768.502123] input: BRLTTY 6.4 Linux Screen Driver Keyboard as /devices/virtual/input/input34
   [ 7768.618382] usb 3-4: usbfs: interface 0 claimed by ch341 while 'brltty' sets config #1
   [ 7768.618952] ch341-uart ttyUSB0: ch341-uart converter now disconnected from ttyUSB0
   [ 7768.618976] ch341 3-4:1.0: device disconnected

To fix this conflict, remove the ``brltty`` package:

.. code-block:: bash

   sudo apt-get remove brltty

Troubleshooting RViz2 Issues
----------------------------------


Set Scale Display Mode to 100%
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you encounter a segmentation fault or see errors such as ``libGL error: failed to create drawable`` when starting RViz2 with the ``-d`` flag,
the issue may be caused by the display scale mode being set to a value other than 100%.

To resolve this issue, set the display scale mode to 100%:

#. Open the system settings on your |Linux| system.
#. Navigate to the **Displays** section.
#. Set the **Scale** option to **100%**.


Enable 3D options in RViz2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

   Displaying in 3D consumes a lot of system resources this may interfere with the robot control commands.
   |intel| recommends opening rviz2 on a development system. The development system needs to be
   in the same network and have the same ROS_DOMAIN_ID set.

   To prepare the development system follow the instructions to :doc:`../../gsg_robot/prepare-system`.

.. code-block:: bash

   # When using different machines, set the same ROS_DOMAIN_ID as on the robot
   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=<YOUR_ROSID>
   rviz2

* open options menu in Rviz2

  .. image:: ../../images/aaeon_rviz2_options.png

* enable 3D display

  .. image:: ../../images/aaeon_rviz2_3Doption_selected.png

Troubleshooting |openvino| Issues
----------------------------------

File Permission Errors
^^^^^^^^^^^^^^^^^^^^^^^
If you encounter an error stating ``permission denied /tmp/pipeline_object.yaml``, you must adjust the file's ownership and permissions accordingly.
The file ownership can be reassigned using the ``chown`` command and file permissions can be adjusted using the ``chmod`` command.
Execute the following commands in your terminal to make the necessary changes:

.. code-block:: bash

   sudo chown $USER /tmp/pipeline_object.yaml
   sudo chmod u+x /tmp/pipeline_object.yaml

The first command assigns the current user as the owner of ``/tmp/pipeline_object.yaml``, while the second command grants the owner execute permissions
for this file. 

Missing Model files 
^^^^^^^^^^^^^^^^^^^^
Some of the |openvino| based tutorials in this SDK rely on the models that are provided during the installation of the ``ros-humble-openvino-node``. In case you missed out on installing these models you may run into problem when executing these tutorials.

Follow the instructions on :doc:`../../gsg_robot/install-openvino`, to troubleshoot potential issues with the |openvino| installation.


.. _troubleshooting-gpu-not-detected:

GPU device is not detected with |Linux| Kernel 6.7.5 or later
--------------------------------------------------------------

According to the |intel_compute_runtime_release_notes_24_09|,
there is a known incompatibility between the |intel| Graphics Compute Runtime
used in this release of the |lp_amr| and the |i915| kernel mode driver in
|Linux| Kernel 6.7.5 or later.

For |core| Ultra Processors, the recommended operating system for the |lp_amr|
is the |ubuntu_iso_download| Desktop image, as described in the
:doc:`../../gsg_robot/prepare-system` section. Since this version of the
|ubuntu| operating system uses a |Linux| Kernel 6.8, this incompatibility
will have an impact if you use the |lp_amr| on an |core| Ultra Processor.

To test whether your system is impacted, you can use the ``clinfo`` tool.
You can install and execute this tool by means of:

.. code-block:: bash

   sudo apt install clinfo
   clinfo | grep "Device Type"

The output of the ``clinfo`` command will report the detected |opencl|
devices:

.. code-block:: text

   Device Type                                     CPU
   Device Type                                     GPU
   Device Type                                     Accelerator

If the list of devices not include the GPU, your system is impacted.

To fix the issue, you can apply the workaround that is recommended in the
|intel_compute_runtime_release_notes_24_09|.
If you export the following debug variables before you run any of the
GPU-related workloads, the GPU will be detected appropriately:

.. code-block:: bash

   export NEOReadDebugKeys=1
   export OverrideGpuAddressSpace=48

