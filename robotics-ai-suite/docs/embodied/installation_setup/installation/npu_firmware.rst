Install Intel® NPU firmware
================================

Introduction
:::::::::::::::::::::::::::

Intel® NPU device is an AI inference accelerator integrated with Intel client CPUs,
starting from Intel® Core™ Ultra generation of CPUs (formerly known as Meteor Lake).
It enables energy-efficient execution of artificial neural network tasks.

To make sure that your system has an NPU available, please follow
`the steps <https://www.intel.com/content/www/us/en/support/articles/000097597/processors.html>`_.

The full device name is Neural Processing Unit, but the |Linux| kernel driver uses
the older name - Versatile Processing Unit (VPU).

Installation
:::::::::::::::::::::::::::

1. Remove old packages

.. code-block:: bash

    $ sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu

2. Download all debs package

.. code-block:: bash

    $ wget https://github.com/intel/linux-npu-driver/releases/download/v1.13.0/intel-driver-compiler-npu_1.13.0.20250131-13074932693_ubuntu22.04_amd64.deb --no-check-certificate
    $ wget https://github.com/intel/linux-npu-driver/releases/download/v1.13.0/intel-fw-npu_1.13.0.20250131-13074932693_ubuntu22.04_amd64.deb --no-check-certificate
    $ wget https://github.com/intel/linux-npu-driver/releases/download/v1.13.0/intel-level-zero-npu_1.13.0.20250131-13074932693_ubuntu22.04_amd64.deb --no-check-certificate

3. Install ``libtbb12`` which is a dependency for ``intel-driver-compiler-npu``

.. code-block:: bash

    $ sudo apt update
    $ sudo apt install libtbb12

4. Install all packages

.. code-block:: bash

    $ sudo dpkg -i *.deb

5. Install Level Zero if it is not in the system

.. code-block:: bash

    # Check if Level Zero is installed
    $ dpkg -l level-zero

Download and install package if Level Zero is missing

.. code-block:: bash

    $ wget https://github.com/oneapi-src/level-zero/releases/download/v1.18.5/level-zero_1.18.5+u22.04_amd64.deb --no-check-certificate
    $ sudo dpkg -i level-zero*.deb

6. Reboot

.. code-block:: bash

    $ reboot
    # if everything works, we should see /dev/accel/accel0 device
    $ ls /dev/accel/accel0
    /dev/accel/accel0
    # to receive intel_vpu state
    $ dmesg | grep intel_vpu

7. User access to the device

As a root user, this step can be skipped.

The new device ``/dev/accel/accel0`` requires manual setting of permissions access.
The ``accel`` devices should be in the "render" group in Ubuntu:

.. code-block:: bash

    # set the render group for accel device
    $ sudo chown root:render /dev/accel/accel0
    $ sudo chmod g+rw /dev/accel/accel0
    # add user to the render group
    $ sudo usermod -a -G render <user-name>
    # user needs to restart the session to use the new group (log out and log in)

The above steps must be repeated each time module is reloaded or on every reboot.
To avoid manual setup of the group for ``accel`` device, the udev rules can be used:

.. code-block:: bash

    $ sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > /etc/udev/rules.d/10-intel-vpu.rules"
    $ sudo udevadm control --reload-rules
    $ sudo udevadm trigger --subsystem-match=accel

.. tip:: In case of NPU is not visible, always check the access to the device with following command:

    .. code-block:: console

        $ ls -lah /dev/accel/accel0
        crw-rw---- 1 root render 261, 0 Mar 22 13:22 /dev/accel/accel0

    If render is missing, or ``crw-rw----`` is not set, please repeat the steps to set the access to the device.