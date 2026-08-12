# Gigabit Multimedia Serial Link Sensor Guide

- **Prerequisite:** Follow the instructions in [Getting Started Guide](../gsg_robot/index.md). To use GMSL cameras, The minimum required setup to get GMSL working is setting up `amrdocs` APT repository, and `kobuk` APT repository.

**Required Packages:**
    - intel-mipi-gmsl-dkms
    - v4l-utils
    - i2c-tools
    - librealsense2
    - libreal

**GMSL (Gigabit Multimedia Serial Link)** is a high-speed serial interface designed for transmitting uncompressed video, audio, and control data over long distances. It is commonly used in automotive applications for connecting cameras and other multimedia devices to the central processing unit.

GMSL supports data rates of up to 6 Gbps, allowing for high-resolution video transmission with low latency. It uses a differential signaling method to ensure signal integrity and reduce electromagnetic interference (EMI). GMSL also includes features such as error correction and power management to enhance reliability and efficiency.

In the context of robotics and autonomous mobile robots, GMSL sensors are often used for vision-based applications, such as object detection, lane keeping, and obstacle avoidance. These sensors can provide high-quality video feeds that are essential for the perception systems of autonomous vehicles.

When integrating GMSL sensors into a robotics system, it is important to consider factors such as compatibility with the processing unit, power requirements, and the physical layout of the system. Proper configuration and calibration of GMSL sensors are also crucial to ensure optimal performance and accurate data capture.

GMSL cameras use the Intel® Image Processor Unit (IPU) to process the video data captured by the camera. The IPU is responsible for tasks such as image enhancement, noise reduction, and color correction, which are essential for improving the quality of the video feed before it is used for further processing in the autonomous mobile robot's perception system.

![GMSL overview](../images/gmsl/GMSL-overview2.png "gmsl overview")

## Next Steps

- [Configure Intel® GMSL `SerDes` ACPI Devices](./gmsl-guide/configure-gmsl-serdes-dev-kit.md)

<!--hide_directive
:::{toctree}
:hidden:

Configure GMSL Dev Kit SerDes ACPI Devices <./gmsl-guide/configure-gmsl-serdes-dev-kit.md>

:::
hide_directive-->