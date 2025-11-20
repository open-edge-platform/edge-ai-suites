Prepare the Target System
##########################

Install Canonical Ubuntu 22.04 LTS (Jammy Jellyfish)
========================================================

It is recommended but not required that your target system has a fresh installation of Canonical Ubuntu 22.04 LTS (Jammy Jellyfish).

You can download Canonical Ubuntu 22.04 LTS (Jammy Jellyfish) from `Ubuntu OS version 22.04 LTS (Jammy Jellyfish) <https://releases.ubuntu.com/22.04>`__.
Visit the Ubuntu website for installation instructions `Install Ubuntu desktop <https://ubuntu.com/tutorials/install-ubuntu-desktop>`__.


Canonical Ubuntu Installation Overview
--------------------------------------------

#. Download the ISO file for `Ubuntu OS version 22.04 LTS (Jammy Jellyfish) <https://releases.ubuntu.com/22.04>`__.

#. Create a bootable flash drive using an imaging application, such as
   Startup Disk Creator, included with your Ubuntu\* installation.

#. After flashing the USB drive, power off your target system, insert
   the USB drive, and power on the target system.

   If the target system does not boot from the USB drive, change the boot
   priority in the system BIOS.

#. Follow the prompts to install Ubuntu\* with the default configurations.

#. Power down your target system and remove the USB drive.

#. Power up the target system and see Ubuntu\* is successfully installed.


Install ROS 2 Humble
============================

To install ROS 2 on your system, follow the `ROS 2 setup guide <https://docs.ros.org/en/humble/Installation.html>`__.


ROS 2 Installation Overview
-------------------------------

When following the `ROS 2 setup with Ubuntu Deb Packages <https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html#ubuntu-debian-packages>`__ the installation
include the following steps:

#. Setup APT sources
#. Install ROS packages using APT
#. Environment setup

.. _prepare-ros-environment-rvc:

Prepare your ROS 2 Environment
-------------------------------
In order to execute any ROS 2 command in a new shell, you first have to source the ROS 2 ``setup.bash`` and set the individual ``ROS_DOMAIN_ID`` for your ROS 2 communication graph.
Get more information about this topic in the `The ROS_DOMAIN_ID <https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html>`__ documentation.

.. code-block:: bash

   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=42

.. note::

   The value 42 serves just as an example. Use an individual ID for every ROS 2 node that is expected to participate in a given ROS 2 graph in order to avoid conflicts in handling messages.


Setup a permanent ROS 2 environment
+++++++++++++++++++++++++++++++++++++

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
