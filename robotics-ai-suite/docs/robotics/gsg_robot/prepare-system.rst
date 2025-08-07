Prepare the Target System
##########################

.. figure:: ../images/system/target.png


Install |ubuntu_version|
========================

Intel recommends a fresh installation of the Ubuntu distribution of the |Linux| OS for your target system, but this is not mandatory.

Depending on your processor type, select one of the following |ubuntu|
22.04 LTS variants:

.. table::

   +----------------------------------------------+------------------------------------------------+
   | Processor type                               | |ubuntu| 22.04 LTS variant                     |
   +==============================================+================================================+
   | |core| Ultra Processors                      | |ubuntu_iso_download| Desktop image            |
   +----------------------------------------------+------------------------------------------------+
   | Other |intel| processors, including:         | 22.04 LTS image for Intel IoT platforms,       |
   |                                              | available at |ubuntu_iot_iso_download|         |
   | 11th/12th/13th Generation |core| Processors, |                                                |
   |                                              |                                                |
   | |intel| Processor N-series                   |                                                |
   | (products formerly Alder Lake-N)             |                                                |
   +----------------------------------------------+------------------------------------------------+

Visit the |ubuntu| website to see the detailed installation instructions: |ubuntu_install_instructions|.

Steps to Install |ubuntu|
-------------------------

#. Download the ISO file from the official website, according to the table above.

#. Create a bootable flash drive by using an imaging application, such as
   Startup Disk Creator, which is available in a standard Ubuntu\* desktop installation.

#. After flashing the USB drive, turn off the target system, insert
   the USB drive, and power it on. If the target system does not boot from the USB drive, change the BIOS settings to prioritize booting from the USB drive.

#. Follow the prompts for installation with default configurations.

#. After installation, power down the system, remove the USB drive and then power up.

#. Verify Ubuntu\* is successfully installed.


Verify that the appropriate |Linux| kernel is installed
-------------------------------------------------------

Run the following command to display the installed |Linux| kernel:

.. code-block:: bash

   uname -r

Depending on the processor type, the expected result is as follows:

.. table::

   +------------------------------------------+--------------------------------------+
   | Processor type                           | Expected kernel version              |
   +==========================================+======================================+
   | |core| Ultra Processors                  | ``6.5.0-44-generic``                 |
   +------------------------------------------+--------------------------------------+
   | Other |intel| processors                 | ``5.15.0-1060-intel-iotg``           |
   +------------------------------------------+--------------------------------------+



.. _install-ros-ros-version:

Install |ros| |ros_version|
============================

To install |ros| on your system, follow the |ros_install_instructions|.


|ros| Installation Overview
-------------------------------

When following the |ros_install_instructions_debian|, typically the installation
includes the following steps:

#. Set up APT sources
#. Install ROS packages using APT
#. Environment setup

.. _prepare-ros-environment:

Prepare your |ros| Environment
-------------------------------
In order to execute any |ros| command in a new shell, you first have to source the |ros| ``setup.bash`` and set the individual ``ROS_DOMAIN_ID`` for your |ros| communication graph.
Get more information about this topic in the `The ROS_DOMAIN_ID <https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html>`__ documentation.

.. code-block:: bash

   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=42

.. note::

   The value 42 serves just as an example. Use an individual ID for every |ros| node that is expected to participate in a given |ros| graph in order to avoid conflicts in handling messages.


Set up a permanent |ros| environment
++++++++++++++++++++++++++++++++++++++

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


