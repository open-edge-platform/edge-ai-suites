:next_page: None
:prev_page: ../packages

.. _ethercat:

EtherCAT Master Stack
######################

The EtherCAT master stack by IgH is used for open source projects for automation of systems such as Robot Operating System (ROS) and LinuxCNC. Applications of an open source–based EtherCAT master system reduces cost and makes application program development flexible.
Based on the native, Intel made the following optimizations:

- Support for |Linux| Kernel 5.x/6.x
- Support for Preempt RT
- Migration to the latest IGB/IGC/mGBE driver to stack

The EtherCAT master stack currently contains the following packages:

``ighethercat:``
  
  This package contains ethercat start/stop service script, utility tool and configuration files for kernel space EtherCAT Stack.

``ighethercat-dpdk:``

  This package contains ethercat utility tool and configuration files for user space EtherCAT Stack.

``ighethercat-dkms:``
  
  This package contains dynamic kernel module for kernel space EtherCAT master module and optimized EtherCAT driver modules for Intel network solutions(IGB/IGC/stmmac)

``ighethercat-examples:``

  This package contains various examples demonstrating use of EtherCAT(kernel space)

``ighethercat-dpdk-examples:``

  This package contains various examples demonstrating use of EtherCAT(user space)

``ecat-enablekit:``

  This package provides a library to enhance IgH EtherCAT Master Stack(kernel space) to support ENI(EtherCAT network information) and ESI(EtherCAT slave information)

``ecat-enablekit-dpdk:``

  This package provides a library to enhance IgH EtherCAT Master Stack(user space) to support ENI(EtherCAT network information) and ESI(EtherCAT slave information)


Quick Start
************

You can install this component from the Intel* Embodied Intelligence SDK repository.

.. code-block:: bash

   $ sudo apt install ighethercat ighethercat-dkms ighethercat-examples ecat-enablekit

Set up EtherCAT Master
------------------------

This section describes the procedure to run IgH EtherCAT Master Stack.

Dependencies
^^^^^^^^^^^^^

* **Native EtherCAT Device Driver** - IGB/IGC (High performance)

  - Only supports IGB, IGC devices (Intel® Ethernet Controller I210, Intel® Ethernet Controller I211, Intel® Ethernet Controller I225/I226) and mGBE devices
  - One networking driver for EtherCAT and non-EtherCAT devices

  Driver gets more complicated, as it must handle EtherCAT and non-EtherCAT devices.

* **Generic EtherCAT Device Driver** - Generic (Low performance)
  - Any Ethernet hardware that is covered by a |Linux| Ethernet driver can be used for EtherCAT
  - Performance is low compared to the native approach, because the frame data have to traverse the lower layers of the network stack

  **Note**: If the target system does not support the IGB/IGC/mGBE device driver, select the generic EtherCAT device driver.


EtherCAT Initialization Script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The EtherCAT master ``init`` script is installed in ``/etc/init.d/ethercat``.

EtherCAT *Sysconfig* File
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ``init`` script uses a mandatory ``sysconfig`` file installed in ``/etc/sysconfig/ethercat``. The ``sysconfig`` file contains the configuration variables needed to operate one or more masters. The documentation is within the file and also included here.

   .. figure:: assets/ethercat/ethercat_sysconfig.png
      :align: center

Do the following:

#. Set **REBIND_NICS**.
   Use ``lspci`` to query net devices. One of the devices might be be specified as an EtherCAT network interface.

   .. figure:: assets/ethercat/lspci.png
      :align: center

#. Fill the MAC address for **MASTER0_DEVICE**.
   Get the MAC address of the Network Interface Controllers (NICs) selected for EtherCAT.

   .. figure:: assets/ethercat/ifconfig.png
      :align: center

   **Note:** EtherCAT Master Stack supports dual master configuration. To configure a second master, fill the MAC address for **MASTER1_DEVICE** and add PCI address in **REBIND_NICS**.

#. Modify **DEVICE_MODULES**:

   - Option 1: Intel Corporation I210 GbE controller EtherCAT driver (High performance)

     .. code-block:: bash

        DEVICE_MODULES="igb"

   - Option 2: Intel Corporation I225 GbE controller EtherCAT driver (High performance)

     .. code-block:: bash

        DEVICE_MODULES="igc"

   - Option 3: Intel® Core™ 12th S-Series [Alder Lake] and 11th Gen P-Series and U-Series [Tiger Lake] Intel® Atom™ x6000 Series [Elkhart Lake] GbE controller EtherCAT driver (High performance)

     .. code-block:: bash

        DEVICE_MODULES="dwmac_intel"

   - Fallback: Generic driver as EtherCAT driver (Low performance)

     .. code-block:: bash

        DEVICE_MODULES="generic"


Start Master as Service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After the ``init`` script and the ``sysconfig`` file are ready to configure, and are placed in the right location, the EtherCAT master can be inserted as a service. You can use the ``init`` script to manually start and stop the EtherCAT master. Execute the ``init`` script with one of the following parameters:

   +-----------------------------------------------+---------------------------------------------------------+
   | Start EtherCAT Master                         |  .. code-block:: bash                                   |
   |                                               |                                                         |
   |                                               |     $ /etc/init.d/ethercat start                        |
   +-----------------------------------------------+---------------------------------------------------------+
   | Stop EtherCAT Master                          |  .. code-block:: bash                                   |
   |                                               |                                                         |
   |                                               |     $ /etc/init.d/ethercat stop                         |
   +-----------------------------------------------+---------------------------------------------------------+
   | Restart EtherCAT Master                       |  .. code-block:: bash                                   |
   |                                               |                                                         |
   |                                               |     $ /etc/init.d/ethercat restart                      |
   +-----------------------------------------------+---------------------------------------------------------+
   | Status of EtherCAT Master                     |  .. code-block:: bash                                   |
   |                                               |                                                         |
   |                                               |     $ /etc/init.d/ethercat status                       |
   +-----------------------------------------------+---------------------------------------------------------+

EtherCAT Configuration & Compilation
------------------------------------------------

By default, Intel Embodied Intelligence SDK provides a generic configuration to enable EtherCAT. EtherCAT stack supports DKMS to build kernel modules whose sources generally reside outside the kernel source tree.

The source code of the EtherCAT stack can be found at: ``/var/lib/dkms/ighethercat-dkms/1.6/source``
The default configuration of EtherCAT stack is located in a file named ``dkms.conf``. The configuration can be modified as needed.

Compiling EtherCAT
^^^^^^^^^^^^^^^^^^

#. Change directory to the EtherCAT source:

   .. code-block:: bash

      $ cd /var/lib/dkms/ighethercat-dkms/1.6/source

#. Modify the default configuration of EtherCAT stack located in ``dkms.conf`` as needed.

#. Rebuild the EtherCAT stack with using the following commands:

  .. code-block:: bash

     $ dkms uninstall ighethercat-dkms -v 1.6
     $ dkms unbuild ighethercat-dkms -v 1.6
     $ dkms build ighethercat-dkms -v 1.6
     $ dkms install ighethercat-dkms -v 1.6

Makefile Template for EtherCAT application
-------------------------------------------

Provided below are some Makefile templates for EtherCAT application. These templates are provided to build EtherCAT application without ``Makefile.am``.

**Makefile template for PREEMPT-RT kernel**

   .. code-block:: console

      CC     = gcc
      CFLAGS = -Wall -O3 -g -D_GNU_SOURCE -D_REENTRANT -fasynchronous-unwind-tables
      LIBS   = -lm -lrt -lpthread -lethercat -Wl,--no-as-needed -L/usr/lib

      TARGET = test
      SRCS   = $(wildcard *.c)

      OBJS   = $(SRCS:.c=.o)

      $(TARGET):$(OBJS)
              $(CC) -o $@ $^ $(LIBS)

      clean:
              rm -rf $(TARGET) $(OBJS)

      %.o:%.c
              $(CC) $(CFLAGS) -o $@ -c $<

**Makefile template for Dovetail kernel**

   .. code-block:: console

      CC     = gcc
      CFLAGS = -Wall -O3 -g -I/usr/include/xenomai/cobalt -I/usr/include/xenomai -D_GNU_SOURCE -D_REENTRANT -fasynchronous-unwind-tables -D__COBALT__ -D__COBALT_WRAP__
      LIBS   = -lm -lrt -lpthread -lethercat_rtdm -Wl,--no-as-needed -Wl,@/usr/lib/cobalt.wrappers -Wl,@/usr/lib/modechk.wrappers  /usr/lib/xenomai/bootstrap.o -Wl,--wrap=main -Wl,--dynamic-list=/usr/lib/dynlist.ld -L/usr/lib -lcobalt -lmodechk

      TARGET = test
      SRCS   = $(wildcard *.c)

      OBJS   = $(SRCS:.c=.o)

      $(TARGET):$(OBJS)
              $(CC) -o $@ $^ $(LIBS)

      clean:
              rm -rf $(TARGET) $(OBJS)

      %.o:%.c
              $(CC) $(CFLAGS) -o $@ -c $<


