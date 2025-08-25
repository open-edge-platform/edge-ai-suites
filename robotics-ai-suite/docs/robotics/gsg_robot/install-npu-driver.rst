Install the |intel| NPU Driver on |core| Ultra Processors
#########################################################

If you want to run |openvino| inferencing applications on the NPU device
of |core| Ultra processors, you need to install the |intel| NPU driver.
If your system does not have an |core| Ultra Processor, you should skip
this step.

General information on the |intel| NPU driver can be found on the
`Linux NPU Driver <https://github.com/intel/linux-npu-driver/releases>`__
website. The driver consists of the following packages:

*  ``intel-driver-compiler-npu``: |intel| driver compiler for NPU hardware;
   the driver compiler enables compilation of |openvino| IR models using
   the Level Zero Graph Extension API.
*  ``intel-fw-npu``: |intel| firmware package for NPU hardware.
*  ``intel-level-zero-npu``: |intel| Level Zero driver for NPU hardware;
   this library implements the Level Zero API to interact with the NPU
   hardware.

.. note::
   The installation instructions on the
   `Linux NPU Driver <https://github.com/intel/linux-npu-driver/releases>`__
   website download the ``*.deb`` files for these components,
   and install the packages from the downloaded files. In consequence, you
   won't get any upgrades for these packages without manual interaction.
   For this reason, it's better to use packages from an APT package feed,
   as it is described in the following.

The packages of the |intel| NPU driver are provided by the
APT package feed, which you have added to your system when you followed
the instructions on page :doc:`./apt-setup`.
This APT package feed also provides all dependencies of the |intel| NPU
driver packages.

To install the |intel| NPU driver, run the commands:

.. code-block:: bash

   sudo apt-get install intel-level-zero-npu intel-driver-compiler-npu

After you have installed the driver and rebooted your system, make sure that
you execute the steps in the "User access to the device" section on the
`Linux NPU Driver <https://github.com/intel/linux-npu-driver/releases>`__
website. These steps include:

*  Add your user account to the ``render`` group:

   .. code-block:: bash

      sudo usermod -a -G render $USER

*  After this step, log-out and log-in again.
   Verify that your account belongs to the ``render`` group now:

   .. code-block:: bash

      groups $USER

*  Set the render group for ``accel`` device:

   .. code-block:: bash

      sudo chown root:render /dev/accel/accel0
      sudo chmod g+rw /dev/accel/accel0

The last step must be repeated each time when the module is reloaded or after every reboot.
To avoid the manual setup of the group for the ``accel`` device, you can
configure the following ``udev`` rules:

.. code-block:: bash

   sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > /etc/udev/rules.d/10-intel-vpu.rules"
   sudo udevadm control --reload-rules
   sudo udevadm trigger --subsystem-match=accel

Now, you can check that the device has been set up with appropriate
access rights. Verify that you can see the ``/dev/accel/accel0`` device
and that the device belongs to the ``render`` group:

.. code-block:: bash
   
   $ ls -lah /dev/accel/accel0
   crw-rw---- 1 root render 261, 0 Jul  1 13:10 /dev/accel/accel0

