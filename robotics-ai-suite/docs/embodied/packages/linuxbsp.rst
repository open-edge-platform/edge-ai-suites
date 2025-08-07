:next_page: None
:prev_page: ../packages

.. _linuxbsp:

|Linux| BSP
############

The Embodied Intelligence SDK includes Intel's LTS Kernel v6.12 with Preempt RT patch to support the Arrow Lake platform, which includes the |Linux| Kernel v6.12, optimized configuration, and kernel boot parameters.

Quick Start
************

You can install this component from Intel's Embodied Intelligence SDK repository.

For RT kernel:

.. code-block:: bash

   $ sudo apt install linux-intel-rt-experimental

For generic kernel:

.. code-block:: bash

   $ sudo apt install linux-intel-experimental

Configure and Build |Linux| Kernel
-----------------------------------

The |Linux| BSP Sources are available to download with ``apt-get source`` in addition to support developer to compile by self and deploy on target.
This section will explain the procedure to configure the |Linux| kernel and build it.

**Step 1: Environment Prerequisites**

In this step, you will set up your build environment.

Install additional packages before building a kernel. To do so, run this command:

.. code-block:: bash

   $ sudo apt-get install git fakeroot build-essential ncurses-dev xz-utils libssl-dev bc flex libelf-dev bison debhelper

The command we used above installs the following packages:

.. include:: bsp_depend.rst

**Step 2: Download the Source Code**

   To use below commands to download and extract the kernel source.

For RT kernel:

   .. code-block:: bash

     $ sudo apt-get source linux-intel-rt-experimental
     $ cd linux-intel-rt-experimental*

For generic kernel:

   .. code-block:: bash

     $ sudo apt-get source linux-intel-experimental
     $ cd linux-intel-experimental*

**Step 3: Configure RT Kernel**

   The |Linux| kernel source code comes with the default configuration. Refer to the following list which provides the additional kernel configurations used during compilation to optimize the system for real-time performance.

    +-------------------------------------------------+-----------------------------------------+
    |  kernel config fragment overrides (.cfg)        | Comments                                |
    +=================================================+=========================================+
    |  .. code-block:: console                        |                                         |
    |                                                 |                                         |
    |     CONFIG_HZ_250=y                             | Reduce task scheduling-clock overhead   |
    |     CONFIG_NO_HZ=n                              | and disable CPU governor |Linux| OS     |
    |     CONFIG_NO_HZ_FULL=y                         | features                                |
    |     CONFIG_NO_HZ_IDLE=n                         |                                         |
    |     CONFIG_ACPI_PROCESSOR=n                     |                                         |
    |     CONFIG_CPU_FREQ_GOV_ONDEMAND=n              |                                         |
    |     CONFIG_CPU_FREQ_DEFAULT_GOV_ONDEMAND=n      |                                         |
    |     CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE=y   |                                         |
    |     CONFIG_CPU_FREQ=n                           |                                         |
    |     CONFIG_CPU_IDLE=n                           |                                         |
    |                                                 |                                         |
    +-------------------------------------------------+-----------------------------------------+
    |  .. code-block:: console                        |                                         |
    |                                                 | Disable |Linux| OS power-management     |
    |     ARCH_SUSPEND_POSSIBLE=n                     | runtime features                        |
    |     CONFIG_SUSPEND=n                            |                                         |
    |     CONFIG_PM=n                                 |                                         |
    |                                                 |                                         |
    +-------------------------------------------------+-----------------------------------------+
    |  .. code-block:: console                        |                                         |
    |                                                 |                                         |
    |      CONFIG_VIRT_CPU_ACCOUNTING=y               | Enable more accurate task and           |
    |      CONFIG_VIRT_CPU_ACCOUNTING_GEN=y           | CPU time accounting                     |
    |                                                 |                                         |
    +-------------------------------------------------+-----------------------------------------+
    |  .. code-block:: console                        |                                         |
    |                                                 |                                         |
    |     CONFIG_CPU_ISOLATION=y                      | Enable more preemptive task scheduling  |
    |     CONFIG_RCU_NOCB_CPU=y                       | policies and CPU temporal-isolation     |
    |     CONFIG_PREEMPT_RCU=y                        |                                         |
    |     CONFIG_HAVE_PREEMPT_LAZY=y                  |                                         |
    |     CONFIG_PREEMPT_LAZY=y                       |                                         |
    |     CONFIG_PREEMPT_RT=y                         |                                         |
    |                                                 |                                         |
    +-------------------------------------------------+-----------------------------------------+ 

    You can find a file named ``config-6.12.8-intel-ese-experimental-lts`` in ``/boot/`` when the target had installed with 'sudo apt install linux-intel-rt-experimental', and copy it into |Linux| kernel source directory.

  #. To make changes to the configuration file, run the make command:

     .. code-block:: bash

        $ make olddefconfig

  #. if you need to modify configuration options by menu, run the ``menuconfig`` command:

     .. code-block:: bash

        $ make menuconfig

  Use the arrows to make a selection or choose **Help** to learn more about the options. When you finish making the changes, select **Save**, and then exit the menu.

  **Note:** Changing settings for some options can lead to a non-functional kernel. If you are unsure what to change, leave the default settings.

**Step 4: Build the kernel**

   Starting building the kernel by running the following command:

      .. code-block:: bash

         $ cp build-full/ltsintelrelease .
         $ make ARCH=x86 bindeb-pkg

**Step 5: Install the kernel**
  
   The process of building and compiling the |Linux| kernel takes some time to complete. you will find kernel debian package which can be installed on target with below commands:

      .. code-block:: bash

         $ sudo dpkg -i *.deb
         $ sudo update-grub

**Step 6. Reboot and Verify Kernel version**

   When you complete the steps above, reboot the machine.

   When the system boots up, verify the kernel version using the ``uname`` command:

      .. code-block:: bash

         $ uname -mrs


Packages
*********

* :ref:`Linux-intel-rt-experimental <linuxbsp>`
* customizations-grub

