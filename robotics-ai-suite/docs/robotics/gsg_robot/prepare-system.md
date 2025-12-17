# Prepare the Target System

## Install Canonical Ubuntu OS

Intel recommends a fresh installation of the Ubuntu distribution of the Linux OS
for your target system, but this is not mandatory.

Install Ubuntu 22.04 (Jammy Jellyfish) or Ubuntu 24.04 (Noble Numat). Your choice of OS version determines the compatible ROS distribution (Humble Hawksbill or Jazzy Jalisco, respectively).

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Ubuntu 24.04**
<!--hide_directive:sync: jazzyhide_directive-->

Depending on your processor type, select one of the following Canonical Ubuntu
24.04 LTS variants:

|Processor type|Canonical Ubuntu 24.04 LTS variant|
|-|-|
|Intel® Core™ Ultra Processors|[Ubuntu OS version 24.04 LTS (Noble Numat)](https://releases.ubuntu.com/24.04) Desktop image|
|Other Intel® processors, including:<br>11th/12th/13th Generation Intel® Core™ Processors,<br>Intel® Processor N-series (products formerly Alder Lake-N)|24.04 LTS image for Intel IoT platforms, available at [Download Ubuntu image for Intel® IoT platforms](https://ubuntu.com/download/iot/intel-iot)|

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Ubuntu 22.04**
<!--hide_directive:sync: humblehide_directive-->

Depending on your processor type, select one of the following Canonical Ubuntu
22.04 LTS variants:

|Processor type|Canonical Ubuntu 22.04 LTS variant|
|-|-|
|Intel® Core™ Ultra Processors|[Ubuntu OS version 22.04 LTS (Jammy Jellyfish)](https://releases.ubuntu.com/22.04) Desktop image|
|Other Intel® processors, including:<br>11th/12th/13th Generation Intel® Core™ Processors,<br>Intel® Processor N-series (products formerly Alder Lake-N)|22.04 LTS image for Intel IoT platforms, available at [Download Ubuntu image for Intel® IoT platforms](https://ubuntu.com/download/iot/intel-iot)|

<!--hide_directive:::
::::hide_directive-->

Visit the Canonical Ubuntu website to see the detailed installation instructions: [Install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop).

### Steps to Install Canonical Ubuntu

1. Download the ISO file from the official website, according to the table above.

2. Create a bootable flash drive by using an imaging application, such as
   Startup Disk Creator, which is available in a standard Ubuntu\* desktop installation.

3. After flashing the USB drive, turn off the target system, insert
   the USB drive, and power it on. If the target system does not boot from the USB drive, change the BIOS settings to prioritize booting from the USB drive.

4. Follow the prompts for installation with default configurations.

5. After installation, power down the system, remove the USB drive and then power up.

6. Verify Ubuntu\* is successfully installed.

### Verify that the appropriate Linux kernel is installed

Run the following command to display the installed Linux kernel:

```bash
uname -r
```

Depending on the processor type, the expected result is as follows:

|Processor type|Expected kernel version|
|-|-|
|Intel® Core™ Ultra Processors|``6.5.0-44-generic``|
|Other Intel® processors|``5.15.0-1060-intel-iotg``|

## Install ROS 2 Distribution

To install ROS 2 on your system, follow the **ROS 2 setup guide**:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

[https://docs.ros.org/en/jazzy/Installation.html](https://docs.ros.org/en/jazzy/Installation.html).

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

[https://docs.ros.org/en/humble/Installation.html](https://docs.ros.org/en/humble/Installation.html).

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

### ROS 2 Installation Overview

When following the **ROS 2 setup with Ubuntu Deb Packages**, typically the installation
includes the following steps:

1. Set up APT sources
2. Install ROS packages using APT
3. Environment setup

You will find the respective setup guides for supported distributions here:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

[https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debians.html#ubuntu-debian-packages](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debians.html#ubuntu-debian-packages)

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

[https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html#ubuntu-debian-packages](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html#ubuntu-debian-packages)

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

### Prepare your ROS 2 Environment

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

#### Set up a permanent ROS 2 environment

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

#### Important Notes

- If you miss to source the ROS 2 setup bash script, you will not be able
  to execute any ROS 2 command.

- If you forget to set a dedicated ``ROS_DOMAIN_ID``, the ROS 2 command will
  be executed and may partially behave as expected. But you have to expect a diversity of
  unexpected behaviors too.

  - Ensure you use the same ``ROS_DOMAIN_ID`` for every ROS 2 node that is
    expected to participate in a given ROS 2 graph.
  - Ensure you use an individual ``ROS_DOMAIN_ID`` for every ROS 2 communication
    graph, in order to avoid conflicts in message handling.
