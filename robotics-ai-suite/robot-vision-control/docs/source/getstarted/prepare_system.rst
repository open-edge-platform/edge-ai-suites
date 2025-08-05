Prepare the Target System
##########################

Install |ubuntu_version|
========================

It is recommended but not required that your target system has a fresh installation of |Ubuntu22|.

You can download |ubuntu_version| from |ubuntu_iso_download|.
Visit the Ubuntu website for installation instructions |ubuntu_install_instructions|.


|ubuntu| Installation Overview
-----------------------------------

#. Download the ISO file for |ubuntu_iso_download|.

#. Create a bootable flash drive using an imaging application, such as
   Startup Disk Creator, included with your Ubuntu\* installation.

#. After flashing the USB drive, power off your target system, insert
   the USB drive, and power on the target system.

   If the target system does not boot from the USB drive, change the boot
   priority in the system BIOS.

#. Follow the prompts to install Ubuntu\* with the default configurations.

#. Power down your target system and remove the USB drive.

#. Power up the target system and see Ubuntu\* is successfully installed.


Install |ros| |ros_version|
============================

To install |ros| on your system, follow the |ros_install_instructions|.


|ros| Installation Overview
-------------------------------

When following the |ros_install_instructions_debian| the installation
include the following steps:

#. Setup APT sources
#. Install ROS packages using APT
#. Environment setup

.. _prepare-ros-environment-rvc:

Prepare your |ros| Environment
-------------------------------
In order to execute any |ros| command in a new shell, you first have to source the |ros| ``setup.bash`` and set the individual ``ROS_DOMAIN_ID`` for your |ros| communication graph.
Get more information about this topic in the `The ROS_DOMAIN_ID <https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html>`__ documentation.

.. code-block:: bash

   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=42

.. note::

   The value 42 serves just as an example. Use an individual ID for every |ros| node that is expected to participate in a given |ros| graph in order to avoid conflicts in handling messages.


Setup a permanent |ros| environment
+++++++++++++++++++++++++++++++++++++

To simplify the handling of your system, you may add these lines to ``~/.bashrc`` file. In this way, the required settings are executed automatically if a new shell is launched.

.. code-block:: bash

   echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
   echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc

Important Notes
++++++++++++++++

.. note::

   If you miss to source the |ros| setup bash script, you will not be able to execute any |ros| command.

.. note::

   If you forget to set a dedicated ``ROS_DOMAIN_ID``, the |ros| command will be executed and may partially behave as expected.
   But you have to expect a diversity of unexpected behaviors too.

   Ensure you use the same ``ROS_DOMAIN_ID`` for every |ros| node that is expected to participate in a given |ros| graph.

   Ensure you use an individual ``ROS_DOMAIN_ID`` for every |ros| communication graph, in order to avoid conflicts in message handling.


