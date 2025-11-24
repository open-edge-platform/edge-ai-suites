# Install Intel® RealSense™ SDK

Intel® RealSense™ SDK 2.0 is a cross-platform library for Intel® RealSense™ depth cameras.
The SDK allows depth and color streaming, and provides intrinsic and extrinsic calibration information.
The library also offers synthetic streams (pointcloud, depth aligned to color and vise-versa), and a built-in
support for record and playback of streaming sessions.

Intel® RealSense™ SDK 2.0 supports Robot Operating System (ROS) and ROS 2, allowing you to access commonly used robotic functionality with ease.

ROS is a set of open-source software libraries and tools that help you build robot applications. For more information, see https://www.ros.org/.

## Installation

1. Register the server's public key:

   ```bash

   sudo mkdir -p /etc/apt/keyrings
   curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null
   ```

2. Ensure that apt HTTPS support is installed:

   ```bash

   sudo apt-get install apt-transport-https
   ```

3. Add the server to the list of repositories:

   ```bash

   echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo `lsb_release -cs` main" | \
   sudo tee /etc/apt/sources.list.d/librealsense.list
   ```

4. Update your apt repository caches after setting up the repositories:

   ```bash

   sudo apt update
   ```

5. Install the RealSense drivers and libraries:

   ```bash
   sudo apt install librealsense2-dkms
   sudo apt install librealsense2=2.55.1-0~realsense.12474
   ```

>  **Attention:**
   The command above has fixed the ``librealsense2`` package version; therefore, you need to install dependent packages, for example ``librealsense2-utils``, ``librealsense2-dev``, and ``librealsense2-gl``.

6. (Optional) Install the ROS wrappers for Intel RealSense depth cameras:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: tab1 hide_directive-->

   ```bash
   sudo apt install ros-jazzy-realsense2-camera
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: tab2 hide_directive-->

   ```bash
   sudo apt install ros-humble-realsense2-camera
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

#. (Optional) Install other tools or packages of Intel RealSense depth cameras:

    See the [installation link](https://github.com/IntelRealSense/librealsense/blob/master/doc/distribution_linux.md)>
    to install librealsense packages and more other tools from Intel® RealSense™ depth camera sources.

## Troubleshooting

### Errors for ``librealsense2-dkms`` installation

If errors occur during ``librealsense2-dkms`` package installation, you have options to fix it:

- Install librealsense SDK by using original Linux drivers.

  Once errors occur during installing ``librealsenses2-dkms`` package, it probably is introduced by unmatched kernel version. You can try the following workaround:

  ```bash

  sudo rm -rf /var/lib/dpkg/info/librealsense2-dkms*
  sudo apt install librealsense2-dkms
  ```

- If the option above doesn't work , try to build and install from the source code.

  Follow the steps in `the link <https://github.com/IntelRealSense/librealsense/blob/development/doc/installation.md>`_ to download the librealsense source code and build it.

### Errors for unmet dependencies

If you encounter unmet dependencies during the installation of ROS wrappers for Intel RealSense depth cameras, for example:

```shell

The following packages have unmet dependencies:
ros-humble-librealsense2-tools : Depends: ros-humble-librealsense2 (= 2.55.1-1eci9) but 2.55.1-1jammy.20241125.233100 is to be installed
E: Unable to correct problems, you have held broken packages.
```

This issue is probably caused by the mismatched versions of the ROS wrapper and the librealsense2 package.
You can try to fix it by specifying the version of the dependent package. You can try the following for the example given above:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item} hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1 hide_directive-->

```bash
sudo apt install ros-jazzy-librealsense2=2.55.1-1eci9
sudo apt install ros-jazzy-librealsense2-tools=2.55.1-1eci9
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: tab2 hide_directive-->

```bash
sudo apt install ros-humble-librealsense2=2.55.1-1eci9
sudo apt install ros-humble-librealsense2-tools=2.55.1-1eci9
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->
