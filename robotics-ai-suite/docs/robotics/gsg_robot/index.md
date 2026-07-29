# Get Started

This Get Started Guide explains how to install the Autonomous Mobile Robot.

## Requirements

- You are familiar with executing Linux commands.
- ROS 2 background strongly recommended.
- [Hardware Requirements](./get-started/requirements_robot.md)

## Express Setup

The Express Setup will use an installation tool to automatically configure and install the necessary content on your system. If you prefer to perform the steps yourself, use the [Step-by-step Setup](#step-by-step-setup) guide.

### 1. Express Setup: Install Canonical Ubuntu OS

Intel recommends a fresh installation of the Ubuntu distribution of the Linux OS
for your target system, but this is not mandatory.

Install Ubuntu 24.04 (Noble Numbat) or 22.04 (Jammy Jellyfish) based on your processor type. Your choice of OS version determines the compatible ROS distribution (Jazzy Jalisco or Humble Hawksbill, respectively).

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Ubuntu 24.04**
<!--hide_directive:sync: jazzyhide_directive-->

Depending on your processor type, select one of the following Canonical Ubuntu 24.04 LTS variants:

|Processor type|Canonical Ubuntu 24.04 LTS variant|ROS2 Compatibility|
|-|-|-|
|Intel® Core™ Ultra Processors|[Ubuntu OS version 24.04 LTS (Noble Numbat)](https://releases.ubuntu.com/24.04) Desktop image|Jazzy|

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive-->  **Ubuntu 22.04**
<!--hide_directive:sync: humblehide_directive-->

Depending on your processor type, select one of the following Canonical Ubuntu 22.04 LTS variants:

|Processor type|Canonical Ubuntu 22.04 LTS variant|ROS2 Compatibility|
|-|-|-|
|11-13th Generation Intel® Core™ Processors,<br>Intel® Processor N-series (products formerly Alder Lake-N)|22.04 LTS image for Intel IoT platforms, available at [Download Ubuntu image for Intel® IoT platforms](https://ubuntu.com/download/iot/intel-iot)|Humble|

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

Visit the Canonical Ubuntu website to see the detailed installation instructions: [Install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop).

### 2. Express Setup: Execute Robotics AI Suite Installer

1. Open a terminal prompt which will be used to execute the remaining steps.

2. Download and execute the Robotics AI Suite Installer.

   ```bash
   wget https://amrdocs.intel.com/downloads/robotics-installer
   wget https://amrdocs.intel.com/downloads/robotics-installer.sha256
   (sha256sum -c robotics-installer.sha256 || \
   (echo "ERROR: SHA sum incorrect"; exit 1)) && \
   chmod +x robotics-installer && \
   sudo -E ./robotics-installer
   ```

   > **Note:** If you are behind a network proxy, make sure you have
   > defined ``http_proxy`` and ``https_proxy`` environment variables

   ![Installer](../images/install/installer_1.png)

3. Select an installation profile to install.

   ![Installer](../images/install/installer_2.png)

4. Enable/Disable optional components.

   ![Installer](../images/install/installer_3.png)

5. The installer will perform pre-flight checks. Ensure that all checks passed, then press ``Enter`` to continue.

   ![Installer](../images/install/installer_4.png)

6. The installer will list all the steps which will be performed. Press ``Enter`` to proceed with the installation.
   The installation may take anywhere from 10 to 30 minutes depending on your network and system performance.

   > **Note:** The installer will first initialize the system by uninstalling any packages with names matching the following patterns:
   > ``*oneapi*`` ``ros-*`` ``intel-igc*`` ``*openvino*`` ``*gazebo*`` ``*realsense*`` ``*level-zero*`` ``libze1``

   ![Installer](../images/install/installer_5.png)

   ![Installer](../images/install/installer_6.png)

7. If the installation is successful, you will see a dialog simliar to the following:

   ![Installer](../images/install/installer_7.png)

### 3. Express Setup: Prepare your ROS 2 Environment

The Robotics AI Suite Installer automatically sets ``ROS_DOMAIN_ID`` environment variable
to a random number between 0 and 100 within your ``.bashrc`` configuration.

To use ROS 2 commands in a new shell, source ROS 2 shell setup script:

```bash
source /opt/ros/jazzy/setup.bash
```

> **Note:** Use an individual ``ROS_DOMAIN_ID`` for every ROS 2
> node that is expected to participate in a given ROS 2 graph in order to avoid conflicts
> in handling messages.

### 4. Express Setup: Next steps

At this point, the setup is complete! For next steps, explore the [Tutorials](../dev_guide/index_tutorials.md) for ready-to-use applications and examples.

## Image Composer Tool Setup

An alternative method for setup is to create a pre-configured OS image with ROS 2 and the appropriate repositories using the Image Composer Tool. This approach is similar to the Express Setup convenience script above, but instead of configuring an existing system, it creates a complete bootable OS image that can be deployed to multiple systems or used for fresh installations.

Image Composer Tool supports creating both ISO images (for installation via USB) and raw disk images (for direct deployment to storage devices or VMs). ISO images are suitable for interactive installations, while raw images can be directly written to storage media or VMs for immediate use. If you prefer to start with a base Ubuntu installation, without needing to reimage a system, use the [Express Setup](#express-setup) or the [Step-by-step Setup](#step-by-step-setup) guide.

For detailed instructions, see the [Image Composer Tool installation guide](https://docs.openedgeplatform.intel.com/dev/image-composer-tool/tutorial/installation.html). An abbreviated ISO image creation follows:

1. Install Go (Go 1.24+ required) + build dependencies:

   ```bash
   sudo apt update && sudo apt install golang-1.24 git systemd-ukify mmdebstrap
   ```

2. Update go path since 1.24 isn't default:

   ```bash
   export PATH=$PATH:/usr/lib/go-1.24/bin
   ```

   Verify that Go 1.24 is now active:

   ```bash
   go version
   ```

   To make this change permanent for future shell sessions, add the export command to your ``~/.bashrc`` file:

   ```bash
   echo 'export PATH=$PATH:/usr/lib/go-1.24/bin' >> ~/.bashrc
   source ~/.bashrc
   ```

3. Clone Image Composer Tool repository:

   ```bash
   git clone https://github.com/open-edge-platform/image-composer-tool.git -b main
   cd image-composer-tool
   ```

4. Build the tool (output: ``./image-composer-tool``):

   ```bash
   go build -buildmode=pie -ldflags "-s -w" ./cmd/image-composer-tool
   ```

5. Build the live-installer (required for ISO images):

   ```bash
   go build -buildmode=pie -o ./build/live-installer -ldflags "-s -w" ./cmd/live-installer
   ```

6. Build ISO image:

   ```bash
   sudo -E ./image-composer-tool build image-templates/ubuntu24-x86_64-robotics-jazzy-iso.yml
   ```

7. Once image is successfully built, modify the below command to point to the built image location (shown after build). Change ``/dev/sdX`` to proper USB drive location (i.e. ``/dev/sdb``). Flash ISO Image to USB drive:

   ```bash
   sudo dd if=builds/robotics-jazzy-ubuntu24-24.04.iso of=/dev/sdX bs=4M status=progress conv=fsync
   ```

8. Boot from the USB drive and install the image to your system.

9. **Setup complete!** Next Steps: Explore the [Tutorials](../dev_guide/index_tutorials.md) for ready-to-use applications and examples.

## Step-by-step Setup

The Step-by-step Setup will present a series of steps to follow which will configure and install the necessary content on your system. If you prefer to perform the steps automatically, use the [Express Setup](#express-setup) guide.

### 1. Install Canonical Ubuntu OS

Intel recommends a fresh installation of the Ubuntu distribution of the Linux OS
for your target system, but this is not mandatory.

Install Ubuntu 24.04 (Noble Numbat) or 22.04 (Jammy Jellyfish) based on your processor type. Your choice of OS version determines the compatible ROS distribution (Jazzy Jalisco or Humble Hawksbill, respectively).

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Ubuntu 24.04**
<!--hide_directive:sync: jazzyhide_directive-->

Depending on your processor type, select one of the following Canonical Ubuntu 24.04 LTS variants:

|Processor type|Canonical Ubuntu 24.04 LTS variant|ROS2 Compatibility|
|-|-|-|
|Intel® Core™ Ultra Processors|[Ubuntu OS version 24.04 LTS (Noble Numbat)](https://releases.ubuntu.com/24.04) Desktop image|Jazzy|

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive-->  **Ubuntu 22.04**
<!--hide_directive:sync: humblehide_directive-->

Depending on your processor type, select one of the following Canonical Ubuntu 22.04 LTS variants:

|Processor type|Canonical Ubuntu 22.04 LTS variant|ROS2 Compatibility|
|-|-|-|
|11-13th Generation Intel® Core™ Processors,<br>Intel® Processor N-series (products formerly Alder Lake-N)|22.04 LTS image for Intel IoT platforms, available at [Download Ubuntu image for Intel® IoT platforms](https://ubuntu.com/download/iot/intel-iot)|Humble|

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

Visit the Canonical Ubuntu website to see the detailed installation instructions: [Install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop).

### 2. Install ROS 2 Distribution

To install ROS 2 on your system, follow the **ROS 2 setup guide**:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

[https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html#ubuntu-deb-packages](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html#ubuntu-deb-packages)

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

[https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html#ubuntu-deb-packages](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html#ubuntu-deb-packages)

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

#### 2.1 Prepare your ROS 2 Environment

In order to execute any ROS 2 command in a new shell, you first have to source
the ROS 2 ``setup.bash`` and set the individual ``ROS_DOMAIN_ID`` for your
ROS 2 communication graph.

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

> **Note:** The value 42 serves just as an example. Use an individual ID for every ROS 2
> node that is expected to participate in a given ROS 2 graph in order to avoid conflicts
> in handling messages.

Get more information about **The ROS_DOMAIN_ID** in:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

[documentation](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Domain-ID.html)

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

[documentation](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html)

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

#### 2.2 Set up a permanent ROS 2 environment

To simplify the handling of your system, you may add these lines to ``~/.bashrc``
file. In this way, the required settings are executed automatically
if a new shell is launched.

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

#### 2.3 Important Notes

To use ROS 2 commands in a new shell, source ROS 2 shell setup script:

```bash
source /opt/ros/jazzy/setup.bash
```

> **Note:** Use an individual ``ROS_DOMAIN_ID`` for every ROS 2
> node that is expected to participate in a given ROS 2 graph in order to avoid conflicts
> in handling messages.

### 3. Set up the Autonomous Mobile Robot APT Repositories

This section explains the procedure to configure the APT package manager to use the hosted APT repositories.

1. Open a terminal prompt which will be used to execute the remaining steps.

2. Download the APT key to the system keyring:

   ```bash
   sudo -E wget -O- https://amrdocs.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-AMR.gpg | sudo tee /usr/share/keyrings/amr-archive-keyring.gpg > /dev/null
   ```

3. Add the signed entry to Autonomous Mobile Robot APT sources and configure the APT client to use the Autonomous Mobile Robot APT repositories:

   ```bash
   echo "deb [signed-by=/usr/share/keyrings/amr-archive-keyring.gpg] https://amrdocs.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) amr main" | sudo tee /etc/apt/sources.list.d/amr.list > /dev/null
   echo "deb-src [signed-by=/usr/share/keyrings/amr-archive-keyring.gpg] https://amrdocs.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) amr main" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null
   ```

4. Configure the Autonomous Mobile Robot APT repository to have higher priority over other repositories:

   ```bash
   echo -e "Package: *\nPin: origin amrdocs.intel.com\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/amr
   ```

5. Configure the APT repository for the Intel® oneAPI Base Toolkit:

   ```bash
   wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
   echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list > /dev/null
   echo -e "Package: intel-oneapi-runtime-*\nPin: version 2025.3.*\nPin-Priority: 1001\n" | sudo tee /etc/apt/preferences.d/oneapi > /dev/null
   echo -e "Package: intel-oneapi-compiler-*\nPin: version 2025.3.*\nPin-Priority: 1001\n" | sudo tee -a /etc/apt/preferences.d/oneapi > /dev/null
   echo -e "Package: intel-oneapi-mkl-*\nPin: version 2025.3.*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/oneapi > /dev/null
   ```

6. For latest Intel silicon support, add the Canonical ``kobuk`` Private Package Archive (PPA):

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo -E add-apt-repository -y ppa:kobuk-team/intel-graphics
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   *``kobuk`` PPA not availble for Ubuntu 22.04.*

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

### 4. Install OpenVINO™ Packages

The following steps will add the OpenVINO™ APT repository to your package management.

1. Install the OpenVINO™ GPG key:

   ```bash
   wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/openvino-archive-keyring.gpg > /dev/null
   ```

2. Add the Deb package sources for OpenVINO™ 2025.
   This will allow you to choose your preferred OpenVINO™ version to be installed.

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2025 ubuntu24 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2025.list
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2025 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2025.list
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

3. Run the following commands to create the file ``/etc/apt/preferences.d/intel-openvino``.

   This will pin the OpenVINO™ version to 2025.3.0. Earlier versions of OpenVINO™
   might not support inferencing on the NPU of Intel® Core™ Ultra processors.

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   echo -e "\nPackage: openvino-libraries-dev\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: openvino\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-jazzy-openvino-wrapper-lib\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-jazzy-openvino-node\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   echo -e "\nPackage: openvino-libraries-dev\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: openvino\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-humble-openvino-wrapper-lib\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-humble-openvino-node\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

   If you decide to use a different OpenVINO™ version, ensure that all four packages
   (``openvino-libraries-dev``, ``openvino``, ``ros-jazzy-openvino-wrapper-lib``,
   and ``ros-jazzy-openvino-node``) are pinned to the same OpenVINO™ version.

#### 4.1 Install the OpenVINO™ Runtime and the ROS 2 OpenVINO™ Toolkit

The following steps will install the OpenVINO™ packages:

1. Ensure all APT repositories are updated:

   ```bash
   sudo apt update
   ```

2. Several Autonomous Mobile Robot tutorials allow you to perform OpenVINO™ inference
   on the integrated GPU device of Intel® processors. To enable this feature, install
   the Intel® Graphics Compute Runtime with the following command:

   ```bash
   sudo apt install -y libze1 libze-intel-gpu1
   ```

3. Install the ``debconf-utilities``:

   ```bash
   sudo apt install debconf-utils
   ```

4. Clear any previous installation configurations:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt purge ros-jazzy-openvino-node
   sudo apt autoremove -y
   echo PURGE | sudo debconf-communicate ros-jazzy-openvino-node
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt purge ros-humble-openvino-node
   sudo apt autoremove -y
   echo PURGE | sudo debconf-communicate ros-humble-openvino-node
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

5. Install the OpenVINO™ Runtime:

   ```bash
   sudo apt install openvino
   ```

6. Install the ROS 2 OpenVINO™ Toolkit:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo -E apt install ros-jazzy-openvino-node
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo -E apt install ros-humble-openvino-node
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

   During the installation of the "openvino-node" package,
   you will be prompted to decide whether to install the OpenVINO™ IR
   formatted models.
   Since some tutorials in the Autonomous Mobile Robot, which are based on OpenVINO™,
   depend on these models; it is crucial to respond with ``Yes`` to this query.

   ![configure_ros-2-openvino-node](../images/configure_ros-humble-openvino-node.png)

#### 4.2 OpenVINO™ Re-Installation and Troubleshooting

If you need to reinstall OpenVINO™ or clean your system after a failed
installation, run the following commands:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
sudo apt purge ros-jazzy-openvino-node
sudo apt autoremove -y
echo PURGE | sudo debconf-communicate ros-jazzy-openvino-node
sudo apt install ros-jazzy-openvino-node
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
sudo apt purge ros-humble-openvino-node
sudo apt autoremove -y
echo PURGE | sudo debconf-communicate ros-humble-openvino-node
sudo -E apt install ros-humble-openvino-node
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

### 5. Install RealSense™ Camera SDK

RealSense™ SDK is a cross-platform library for RealSense™
depth cameras. The SDK allows depth and color streaming, and provides
intrinsic and extrinsic calibration information. The library also offers
synthetic streams (pointcloud, depth aligned to color and vise-versa), and a
built-in support for record and playback of streaming sessions.

RealSense™ SDK includes support for ROS and ROS 2, allowing you
access to commonly used robotic functionality with ease.

1. Register the server’s public key:

   ```bash
   sudo mkdir -p /etc/apt/keyrings
   curl -sSf https://librealsense.realsenseai.com/Debian/librealsenseai.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/librealsenseai.gpg > /dev/null
   ```

2. Add RealSense to the list of repositories:

   ```bash
   echo "deb [signed-by=/etc/apt/keyrings/librealsenseai.gpg] https://librealsense.realsenseai.com/Debian/apt-repo `lsb_release -cs` main" | sudo tee /etc/apt/sources.list.d/librealsense.list
   ```

3. Update your APT repository caches after setting up the repository:

   ```bash
   sudo apt update
   ```

4. Install the RealSense drivers and libraries:

   <!--hide_directive:::::{tab-set}hide_directive-->
   <!--hide_directive::::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get install -y --allow-downgrades ros-jazzy-librealsense2
   sudo apt install librealsense2-dkms
   sudo apt install librealsense2
   ```

   <!--hide_directive::::hide_directive-->
   <!--hide_directive::::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get install -y --allow-downgrades ros-humble-librealsense2
   sudo apt install librealsense2-dkms
   sudo apt install librealsense2
   ```

   <!--hide_directive::::hide_directive-->
   <!--hide_directive:::::hide_directive-->

   > **Note:** The pinned version ensures stability across tutorials. To upgrade in the future, update the version in `/etc/apt/preferences.d/librealsense` before installing.

### 6. Install Autonomous Mobile Robot Deb packages

This section details steps to install Autonomous Mobile Robot Deb packages.

1. Before using the Autonomous Mobile Robot APT repositories, update the APT packages list:

   ```bash
   sudo apt update
   ```

   The APT package manager will download the latest list of packages available for all configured repositories.

   ![apt-update](../images/download/apt-update.png)

2. Follow the instructions to install Gazebo:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get update
   sudo apt-get install curl lsb-release gnupg

   sudo -E curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
   sudo apt-get update
   sudo apt-get install gz-harmonic
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get update
   sudo apt-get install curl lsb-release gnupg

   sudo -E add-apt-repository ppa:openrobotics/gazebo11-gz-cli
   sudo -E curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
   sudo apt-get update
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

3. Choose the Autonomous Mobile Robot Deb package to install.

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   **ros-jazzy-robotics-sdk**
      The standard version of the Autonomous Mobile Robot. This package includes almost everything except for a handful of tutorials and bag files.

   **ros-jazzy-robotics-sdk-complete**
      The complete version of the Autonomous Mobile Robot. It also includes those items excluded from the standard version. Please note that the complete SDK downloads approximately 20GB of additional files.

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   **ros-humble-robotics-sdk**
      The standard version of the Autonomous Mobile Robot. This package includes almost everything except for a handful of tutorials and bag files.

   **ros-humble-robotics-sdk-complete**
      The complete version of the Autonomous Mobile Robot. It also includes those items excluded from the standard version. Please note that the complete SDK downloads approximately 20GB of additional files.

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

4. Install the chosen Autonomous Mobile Robot Deb package

   Install command example:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt install ros-jazzy-robotics-sdk
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   Intel oneAPI requires GCC >= 12, so upgrade GCC as well.

   ```bash
   sudo apt install gcc-12 g++-12
   sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 60 --slave /usr/bin/g++ g++ /usr/bin/g++-12
   sudo apt install ros-humble-robotics-sdk
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

   The standard version of the Autonomous Mobile Robot should generally download and install
   all files within just a few minutes. The complete version of the Autonomous Mobile Robot will take
   several more minutes and consume significantly more network bandwidth.

   The actual installation time will vary greatly based primarily upon the number of packages that
   need to be installed and the network connection speed.

   ![apt-install-ros-pkt](../images/download/apt-install-ros-pkt.png)

5. Install one of the following packages based upon your processor type:

   - Intel SSE-only CPU instruction accelerated package for Collaborative SLAM (installed by default):

     <!--hide_directive:::::{tab-set}hide_directive-->
     <!--hide_directive::::{tab-item}hide_directive--> **Jazzy**
     <!--hide_directive:sync: jazzyhide_directive-->

     ```bash
     # Required for Intel® Atom® processor-based systems
     sudo apt-get install ros-jazzy-collab-slam-sse
     ```

     <!--hide_directive::::hide_directive-->
     <!--hide_directive::::{tab-item}hide_directive--> **Humble**
     <!--hide_directive:sync: humblehide_directive-->

     ```bash
     # Required for Intel® Atom® processor-based systems
     sudo apt-get install ros-humble-collab-slam-sse
     ```

     <!--hide_directive::::hide_directive-->
     <!--hide_directive:::::hide_directive-->

   - Intel AVX2 CPU instruction accelerated package for Collaborative SLAM:

     <!--hide_directive:::::{tab-set}hide_directive-->
     <!--hide_directive::::{tab-item}hide_directive--> **Jazzy**
     <!--hide_directive:sync: jazzyhide_directive-->

     ```bash
     # Works only on Intel® Core™ processor-based systems
     sudo apt-get install ros-jazzy-collab-slam-avx2
     ```

     <!--hide_directive::::hide_directive-->
     <!--hide_directive::::{tab-item}hide_directive--> **Humble**
     <!--hide_directive:sync: humblehide_directive-->

     ```bash
     # Works only on Intel® Core™ processor-based systems
     sudo apt-get install ros-humble-collab-slam-avx2
     ```

     <!--hide_directive::::hide_directive-->
     <!--hide_directive:::::hide_directive-->

   - Intel GPU Level-Zero accelerated package for Collaborative SLAM:

     <!--hide_directive:::::{tab-set}hide_directive-->
     <!--hide_directive::::{tab-item}hide_directive--> **Jazzy**
     <!--hide_directive:sync: jazzyhide_directive-->

     ```bash
     # Works only on Intel® Core™ processors with Intel® Xe Integrated Graphics or Intel® UHD Graphics
     sudo apt-get install ros-jazzy-collab-slam-lze
     ```

     <!--hide_directive::::hide_directive-->
     <!--hide_directive::::{tab-item}hide_directive--> **Humble**
     <!--hide_directive:sync: humblehide_directive-->

     ```bash
     # Works only on Intel® Core™ processors with Intel® Xe Integrated Graphics or Intel® UHD Graphics
     sudo apt-get install ros-humble-collab-slam-lze
     ```

     <!--hide_directive::::hide_directive-->
     <!--hide_directive:::::hide_directive-->

     During the installation of the above packages, you will see a dialogue
     asking you for the GPU generation of your system:

     ![debconf_liborb-lze](../images/debconf_liborb-lze.png)

     In this dialogue, select the GPU Generation according to the following table
     depending on your processor type. If you are unsure, it's safe to select
     ``genXe``.

     |GPU Generation|Processors|
     |-|-|
     |``genXe``|Intel® Core™ Ultra Processors<br>11-13th Generation Intel® Core™ Processors<br>Intel® Processor N-series (products formerly Alder Lake-N)|
     |``gen11``|Products formerly Ice Lake|
     |``gen9``|Products formerly Skylake|

     If you want to redisplay this dialogue, you have to uninstall the
     ``liborb-lze`` package using the commands below. This will also remove
     the packages that depend on the ``liborb-lze`` package.
     Then you can install the ``liborb-lze`` package again and the dialogue will
     be redisplayed:

     ```bash
     sudo apt remove --purge liborb-lze
     echo PURGE | sudo debconf-communicate liborb-lze
     sudo apt install liborb-lze
     ```

     Since the ``liborb-lze`` package is one of the fundamental dependencies of
     the Autonomous Mobile Robot, you will have to re-install the Intel GPU
     Level-Zero accelerated package for Collaborative SLAM
     (``ros-jazzy-collab-slam-lze``) as described above.

### 7. Install the Intel® NPU Driver on Intel® Core™ Ultra Processors

If you want to run OpenVINO™ inferencing applications on the NPU device
of Intel® Core™ Ultra processors, you need to install the Intel® NPU driver.
If your system does not have an Intel® Core™ Ultra Processor, you should skip
this step.

General information on the Intel® NPU driver can be found on the
[Linux NPU Driver](https://github.com/intel/linux-npu-driver/releases)
website. The driver consists of the following packages:

- ``intel-driver-compiler-npu``: Intel® driver compiler for NPU hardware;
  the driver compiler enables compilation of OpenVINO™ IR models using
  the Level Zero Graph Extension API.

- ``intel-fw-npu``: Intel® firmware package for NPU hardware.

- ``intel-level-zero-npu``: Intel® Level Zero driver for NPU hardware;
  this library implements the Level Zero API to interact with the NPU
  hardware.

> **Note:** The installation instructions on the
> [Linux NPU Driver](https://github.com/intel/linux-npu-driver/releases)
> website download the ``*.deb`` files for these components,
> and install the packages from the downloaded files. In consequence, you
> won't get any upgrades for these packages without manual interaction.
> For this reason, it's better to use packages from an APT package feed,
> as it is described in the following.

The packages of the Intel® NPU driver are provided by the
APT package feed, which you have added to your system when you setup
the APT package repositories earlier. This APT package feed also provides
all dependencies of the Intel® NPU driver packages.

To install the Intel® NPU driver, complete the following steps:

1. Install the NPU packages:

   ```bash
   sudo apt-get install intel-level-zero-npu intel-driver-compiler-npu
   ```

2. Add your user account to the ``render`` group:

   ```bash
   sudo usermod -a -G render $USER
   ```

3. After this step, log-out (or reboot) and log-in again.
   Verify that your account belongs to the ``render`` group now:

   ```bash
   groups $USER
   ```

4. Set the render group for ``accel`` device:

   ```bash
   sudo chown root:render /dev/accel/accel0
   sudo chmod g+rw /dev/accel/accel0
   ```

   This step must be repeated each time when the module is reloaded or after every reboot.
   To avoid the manual setup of the group for the ``accel`` device, you can
   configure the following ``udev`` rules:

   ```bash
   sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > /etc/udev/rules.d/10-intel-vpu.rules"
   sudo udevadm control --reload-rules
   sudo udevadm trigger --subsystem-match=accel
   ```

   Now, you can check that the device has been set up with appropriate
   access rights. Verify that you can see the ``/dev/accel/accel0`` device
   and that the device belongs to the ``render`` group:

   ```bash
   ls -lah /dev/accel/accel0
   crw-rw---- 1 root render 261, 0 Jul  1 13:10 /dev/accel/accel0
   ```

### 8. Reboot to load latest Linux kernel and firmware

```bash
sudo reboot
```

### 9. Next steps

At this point, the setup is complete! For next steps, explore the [Tutorials](../dev_guide/index_tutorials.md) for ready-to-use applications and examples.

## Optional - Enabling Intel® Silcon on Ubuntu 22.04

If you are using Intel® silcon on an Ubuntu 22
and are having trouble getting the Intel® GPU functioning, you may
need to install a newer Linux kernel, firmware, and GPU drivers from
development.

1. Download the ECI APT key to the system keyring:

   ```bash
   sudo -E wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null
   ```

2. Add the signed entry to ECI APT sources and configure the APT client to use the ECI APT repository:

   ```bash
   echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null
   echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null
   ```

3. Configure the ECI APT repository to have higher priority over other repositories:

   ```bash
   echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" | sudo tee /etc/apt/preferences.d/isar
   ```

4. For latest Intel silicon support, add the Canonical ``kisak`` Private Package Archives (PPA):

   ```bash
   sudo -E add-apt-repository -y ppa:kisak/kisak-mesa
   ```

5. Install mesa packages from ``kisak`` PPA:

   ```bash
   sudo apt install libegl-mesa0 libgl1-mesa-dri libgbm1 libglx-mesa0 mesa-va-drivers mesa-va-drivers mesa-vdpau-drivers mesa-vulkan-drivers xwayland
   ```

6. Install the latest supported Linux kernel:

   ```bash
   sudo apt install linux-intel-experimental
   ```

7. Install the ``eci-customizations`` package to populate the GRUB menu:

   ```bash
   sudo apt install eci-customizations
   ```

8. Install Linux firmware package:

   ```bash
   sudo apt install linux-firmware
   ```

9. Reboot the system to allow the kernel and firmware to load.

## Optional - Enabling Real-time Linux kernel

1. Download the ECI APT key to the system keyring:

   ```bash
   sudo -E wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null
   ```

2. Add the signed entry to ECI APT sources and configure the APT client to use the ECI APT repository:

   ```bash
   echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null
   echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null
   ```

3. Configure the ECI APT repository to have higher priority over other repositories:

   ```bash
   echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" | sudo tee /etc/apt/preferences.d/isar
   ```

4. Install the latest supported real-time Linux kernel:

   ```bash
   sudo apt install linux-intel-rt-experimental
   ```

5. Install the ``eci-customizations`` package to populate the GRUB menu:

   ```bash
   sudo apt install eci-customizations
   ```

6. Install Linux firmware package:

   ```bash
   sudo apt install linux-firmware
   ```

7. Reboot the system to allow the real-time Linux kernel to boot.

## Installation Troubleshooting

### Support Forum

If you encounter difficulties, visit the [Support Forum](https://community.intel.com/t5/Edge-Software-Catalog/bd-p/EdgeSoftwareCatalog) for assistance.

### APT Package Manager

If the APT package manager is unable to connect to the repositories, follow these APT troubleshooting tips:

- Make sure that the system has network connectivity.
- Make sure that port 80 is not blocked by a firewall.
- Configure an APT proxy (if network traffic routes through a proxy server).

    - To configure an APT proxy, add the following lines to a file at
      `/etc/apt/apt.conf.d/proxy.conf` (replace the placeholder as per your specific user and proxy server)::

      ```bash
      Acquire:http:Proxy "http://user:password@proxy.server:port/";
      Acquire:https:Proxy "http://user:password@proxy.server:port/";
      ```

    - To ensure proper proxy settings for other tools required during the package installation
      add the the required proxy settings to `/etc/environment`:

      ```bash
      http_proxy=http://user:password@proxy.server:port
      https_proxy=http://user:password@proxy.server:port
      no_proxy="localhost,127.0.0.1,127.0.0.0/8"
      ```

     After setting the proxy values in `/etc/apt/apt.conf.d/proxy.conf` and `/etc/environment`
     you will have to reboot the device, so these settings become effective.

<!--hide_directive
:::{toctree}
:hidden:

get-started/requirements_robot.md

:::
hide_directive-->
