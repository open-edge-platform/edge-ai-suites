:next_page: None
:prev_page: ../packages

.. _ethercat:

EtherCAT Master Stack
######################

Overview
*********

The EtherCAT master stack by IgH is used for open source projects for automation of systems such as Robot Operating System (ROS) and LinuxCNC. Applications of an open source–based EtherCAT master system reduces cost and makes application program development flexible.
Based on the native, Intel made the following optimizations:

- Support for |Linux| Kernel 5.x/6.x
- Support for Preempt RT
- Migration to the latest IGB/IGC/mGBE driver to stack

EtherCAT Master User Space Stack
***********************************

The EtherCAT Master User Space Stack is an optimized version of the IgH EtherCAT Master Stack designed to run in user space on systems with the Preempt RT patch. This optimization eliminates the need for ioctl system calls, which can introduce latency, thereby improving performance. By maintaining all APIs from the original IgH EtherCAT Master Stack, this user space stack ensures compatibility with existing EtherCAT application programs, allowing for seamless integration and transition.

Key features of the EtherCAT Master User Space Stack include:

- **Latency Improvement:** By avoiding ioctl system calls, the stack reduces latency, which is crucial for real-time applications.
- **Compatibility:** The stack retains all APIs from the original IgH EtherCAT Master Stack, ensuring that existing EtherCAT applications can run without modification.
- **Containerization:** The stack is designed to be easily containerized, facilitating deployment in modern software environments that use containers for isolation and scalability.
- **Multiple Master Support:** The stack supports multiple EtherCAT masters, allowing for complex network configurations and improved scalability.

Overall, this user space stack provides a robust solution for real-time EtherCAT applications, offering improved performance and flexibility while maintaining compatibility with existing software.

EtherCAT Enablekit
*************************

**EtherCAT Enablekit** streamlines the configuration and development of EtherCAT systems by offering a comprehensive set of tools and APIs. It simplifies the setup of EtherCAT masters, slaves, and network topology, allowing developers to focus on application logic rather than low-level configuration details. With Ecat EnableKit, building robust EtherCAT applications becomes faster and more efficient.

Key features of the EtherCAT Enablekit include:

- Built on the IgH EtherCAT Master Stack
- Supports both Preempt-RT and Xenomai/Dovetail real-time frameworks
- Provides utilities to parse EtherCAT Network Information (ENI) files
- Includes tools for parsing EtherCAT Slave Information (ESI) files
- Offers user-friendly APIs for rapid EtherCAT application development
- Supplies example code for controlling EtherCAT IO slaves
- Includes example code for operating EtherCAT CoE slaves (SOE currently not supported)

The architecture is as following:

.. figure:: assets/ethercat/arch.png
   :align: center

Packages
**************

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

Kernel Space Stack
-------------------

You can install this component from the Intel* Embodied Intelligence SDK repository.

.. code-block:: bash

   $ sudo apt install ighethercat ighethercat-dkms ighethercat-examples ecat-enablekit

Set up EtherCAT Master
+++++++++++++++++++++++

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
^^^^^^^^^^^^^^^^^^^^^^^^^^

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
++++++++++++++++++++++++++++++++++++++

By default, Intel Embodied Intelligence SDK provides a generic configuration to enable EtherCAT. EtherCAT stack supports DKMS to build kernel modules whose sources generally reside outside the kernel source tree.

The source code of the EtherCAT stack can be found at: ``/var/lib/dkms/ighethercat-dkms/1.6/source``
The default configuration of EtherCAT stack is located in a file named ``dkms.conf``. The configuration can be modified as needed.

Compiling EtherCAT
^^^^^^^^^^^^^^^^^^^^

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

User Space Stack
-------------------

You can install this component from the Intel* Embodied Intelligence SDK repository.

.. code-block:: bash

   $ sudo apt install ighethercat-dpdk ighethercat-dpdk-examples ecat-enablekit-dpdk

Set up EtherCAT Master
+++++++++++++++++++++++

This section describes the procedure to run EtherCAT Master User Space Stack.   

EtherCAT *Sysconfig* File
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``ecrt.conf`` file located at ``/etc/sysconfig/`` is a crucial configuration file for setting up EtherCAT master nodes. This file contains the necessary configuration variables to operate one or more EtherCAT masters effectively. Make sure to customize below parameters based on your hardware setup and operational needs.

The following describes the configuration parameters that can be defined within the **ethercat** section:

**node_id:**

   This parameter assigns a unique identifier to each EtherCAT master node. The ``node_id`` is essential for distinguish between different nodes, especially in setups involving multiple masters or when managing several EtherCAT networks. Each node should have a distinct ID to ensure proper communication and control within the network.

**master_mac:**

   This specifies the MAC address of the network interface card (NIC) that the EtherCAT master will use for communication. The MAC address is a unique identifier for network devices, ensuring that each master can be correctly identified on the network. If you are using multiple master within a single EtherCAT application, you can register multiple MAC addresses as a list. This allows for flexible configurations and supports complex network setups.

**debug_level:**

   This setting controls the verbosity of debug information output by the EtherCAT master. A debug level of ``0`` means no debug information will be printed, which is suitable for production environments where performance is prioritized. Higher debug levels(up to ``2``) provide more detailed logs, which can be invaluable during development or troubleshooting to understand the system's behavior and diagnose issues.

**drv_argv:**

   This parameter allows you to add extra Environment Abstraction Layer(**EAL**) for the Data Plane Development Kit(**DPDK**) framework. **DPDK** is a set of libraries and drivers for fast packet processing, and **EAL** parameters help configure its operation. For detailed information on available **EAL** parameters and their usage, you can refer to the official **DPDK** documentation at `EAL parameters <https://doc.dpdk.org/guides/linux_gsg/linux_eal_parameters.html>`_. This flexibility enables you to optimize the performance and behavior of the EtherCAT master according to your specific requirements.

vfio binding
^^^^^^^^^^^^^^^^^^^^^^^^^^

As EtherCAT Master User Space Stack requires **DPDK** support for efficient EtherCAT communication, leveraging the ``vfio-pci`` driver as a kernel module for DPDK-bound ports. This setup is crucial for achieving high-performance packet processing, which is essential in real-time applications like EtherCAT. If an IOMMU is unavailable, the ``vfio-pci`` can used in `no-iommu <https://doc.dpdk.org/guides/linux_gsg/linux_drivers.html#vfio-noiommu>`_ mode.

To enable **DPDK** to manage network ports, a utility script called ``dpdk-driver-bind.sh`` is provided to facilitate the binding and unbinding ``vfio-pci`` process for specify EtherCAT ports.

- Binding ``vfio-pci`` on EtherCAT ports

   .. code-block:: bash
   
      dpdk-driver-bind.sh start <EtherCAT port BDF address>
- Unbinding ``vfio-pci`` on EtherCAT ports

   .. code-block:: bash
   
      dpdk-driver-bind.sh stop <EtherCAT port BDF address>
