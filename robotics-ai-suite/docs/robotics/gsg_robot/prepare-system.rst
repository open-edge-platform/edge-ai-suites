Prepare the Target System
##########################

.. figure:: ../images/system/target.png


Install Canonical Ubuntu 22.04 LTS (Jammy Jellyfish)
=========================================================

Intel recommends a fresh installation of the Ubuntu distribution of the Linux OS for your target system, but this is not mandatory.

Depending on your processor type, select one of the following Canonical Ubuntu
22.04 LTS variants:

.. table::

   +----------------------------------------------------+----------------------------------------------------------------------------------------------------------------+
   | Processor type                                     | Canonical Ubuntu 22.04 LTS variant                                                                             |
   +====================================================+================================================================================================================+
   | Intel® Core™ Ultra Processors                      | `Ubuntu OS version 22.04 LTS (Jammy Jellyfish) <https://releases.ubuntu.com/22.04>`__ Desktop image            |
   +----------------------------------------------------+----------------------------------------------------------------------------------------------------------------+
   | Other Intel® processors, including:                | 22.04 LTS image for Intel IoT platforms,                                                                       |
   |                                                    | available at `Download Ubuntu image for Intel® IoT platforms <https://ubuntu.com/download/iot/intel-iot>`__    |
   | 11th/12th/13th Generation Intel® Core™ Processors, |                                                                                                                |
   |                                                    |                                                                                                                |
   | Intel® Processor N-series                          |                                                                                                                |
   | (products formerly Alder Lake-N)                   |                                                                                                                |
   +----------------------------------------------------+----------------------------------------------------------------------------------------------------------------+

Visit the Canonical Ubuntu website to see the detailed installation instructions: `Install Ubuntu desktop <https://ubuntu.com/tutorials/install-ubuntu-desktop>`__.

Steps to Install Canonical Ubuntu
---------------------------------------

#. Download the ISO file from the official website, according to the table above.

#. Create a bootable flash drive by using an imaging application, such as
   Startup Disk Creator, which is available in a standard Ubuntu\* desktop installation.

#. After flashing the USB drive, turn off the target system, insert
   the USB drive, and power it on. If the target system does not boot from the USB drive, change the BIOS settings to prioritize booting from the USB drive.

#. Follow the prompts for installation with default configurations.

#. After installation, power down the system, remove the USB drive and then power up.

#. Verify Ubuntu\* is successfully installed.


Verify that the appropriate Linux kernel is installed
-------------------------------------------------------

Run the following command to display the installed Linux kernel:

.. code-block:: bash

   uname -r

Depending on the processor type, the expected result is as follows:

.. table::

   +------------------------------------------+--------------------------------------+
   | Processor type                           | Expected kernel version              |
   +==========================================+======================================+
   | Intel® Core™ Ultra Processors            | ``6.5.0-44-generic``                 |
   +------------------------------------------+--------------------------------------+
   | Other Intel® processors                  | ``5.15.0-1060-intel-iotg``           |
   +------------------------------------------+--------------------------------------+



.. _install-ros-ros-version:

Install ROS 2 Humble
============================

To install ROS 2 on your system, follow the `ROS 2 setup guide <https://docs.ros.org/en/humble/Installation.html>`__.


ROS 2 Installation Overview
-------------------------------

When following the `ROS 2 setup with Ubuntu Deb Packages <https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html#ubuntu-debian-packages>`__, typically the installation
includes the following steps:

#. Set up APT sources
#. Install ROS packages using APT
#. Environment setup

.. _prepare-ros-environment:

Prepare your ROS 2 Environment
-------------------------------
In order to execute any ROS 2 command in a new shell, you first have to source the ROS 2 ``setup.bash`` and set the individual ``ROS_DOMAIN_ID`` for your ROS 2 communication graph.
Get more information about this topic in the `The ROS_DOMAIN_ID <https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html>`__ documentation.

.. code-block:: bash

   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=42

.. note::

   The value 42 serves just as an example. Use an individual ID for every ROS 2 node that is expected to participate in a given ROS 2 graph in order to avoid conflicts in handling messages.


Set up a permanent ROS 2 environment
++++++++++++++++++++++++++++++++++++++

To simplify the handling of your system, you may add these lines to ``~/.bashrc`` file. In this way, the required settings are executed automatically if a new shell is launched.

.. code-block:: bash

   echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
   echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc

Important Notes
++++++++++++++++

.. note::

   If you miss to source the ROS 2 setup bash script, you will not be able to execute any ROS 2 command.

.. note::

   If you forget to set a dedicated ``ROS_DOMAIN_ID``, the ROS 2 command will be executed and may partially behave as expected.
   But you have to expect a diversity of unexpected behaviors too.

   Ensure you use the same ``ROS_DOMAIN_ID`` for every ROS 2 node that is expected to participate in a given ROS 2 graph.

   Ensure you use an individual ``ROS_DOMAIN_ID`` for every ROS 2 communication graph, in order to avoid conflicts in message handling.
