Install Intel(R) Realsense SDK
###############################

Intel® RealSense™ SDK 2.0 is a cross-platform library for Intel® RealSense™ depth cameras.
The SDK allows depth and color streaming, and provides intrinsic and extrinsic calibration information.
The library also offers synthetic streams (pointcloud, depth aligned to color and vise-versa), and a built-in
support for record and playback of streaming sessions.

Intel® RealSense™ SDK 2.0 includes support for ROS and ROS 2, allowing you access to commonly used robotic functionality with ease.

The Robot Operating System (ROS) is a set of software libraries and tools that help you build robot applications. From drivers to state-of-the-art algorithms, and with powerful developer tools, ROS has what you need for your next robotics project. And it's all open source.
More information about ROS can be found at: https://www.ros.org/

Installation
============

#. Register the server's public key:

    .. code-block:: bash

        $ sudo mkdir -p /etc/apt/keyrings
        $ curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null

#. Make sure apt HTTPS support is installed:

    .. code-block:: bash

        $ sudo apt-get install apt-transport-https

#. Add the server to the list of repositories:

    .. code-block:: bash

        $ echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo `lsb_release -cs` main" | \
        sudo tee /etc/apt/sources.list.d/librealsense.list

#. Update your apt repository caches after setting up the repositories.

    .. code-block:: bash

        $ sudo apt update

#. Install the RealSense drivers and libraries by running the below command:

    .. code-block:: bash

        $ sudo apt install librealsense2-dkms
        $ sudo apt install librealsense2

#. [Optional] Install the ROS wrappers for RealSense by running the below command:

    .. code-block:: bash

        $ sudo apt install ros-humble-realsense2-camera

#. [Optional] Install other tools or packages of RealSense Cameras:

    Please follow `the installation link <https://github.com/IntelRealSense/librealsense/blob/master/doc/distribution_linux.md>`_
    to install librealsense packages and more other tools from Intel RealSense sources.

Troubleshooting
===============

Errors for ``librealsense2-dkms`` installation
:::::::::::::::::::::::::::::::::::::::::::::::

If errors occur during ``librealsense2-dkms`` package installation, you have options to fix it:

- Install librealsense SDK by using original |Linux| drivers

    Once errors occur during installing ``librealsenses2-dkms`` package, it probably is introduced by unmatched kernel version. You can try the below steps for a work-around:

    .. code-block:: bash

        $ sudo rm -rf /var/lib/dpkg/info/librealsense2-dkms*
        $ sudo apt install librealsense2-dkms

- If the above option doesn't work , try to build and install from source code

    Follow the steps in `the link <https://github.com/IntelRealSense/librealsense/blob/development/doc/installation.md>`_ to download librealsense source code and build it.

Errors for unmet dependencies
::::::::::::::::::::::::::::::

If you encounter unmet dependencies during the installation of ROS wrappers for RealSense, taking below log as an example:

.. code-block:: console

    The following packages have unmet dependencies:
    ros-humble-librealsense2-tools : Depends: ros-humble-librealsense2 (= 2.55.1-1eci9) but 2.55.1-1jammy.20241125.233100 is to be installed
    E: Unable to correct problems, you have held broken packages.

It probably is caused by the mismatched versions of the ROS wrapper and the librealsense2 package from different packages sources.
You can try to fix it by specifying the version of the dependent package. You can try below command for the above example:

.. code-block:: bash

    $ sudo apt install ros-humble-librealsense2=2.55.1-1eci9
    $ sudo apt install ros-humble-librealsense2-tools=2.55.1-1eci9
