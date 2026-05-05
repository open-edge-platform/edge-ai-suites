# Gigabit Multimedia Serial Link Sensor Guide

- **Prerequisite:** Follow the instructions in [Getting Started Guide](../gsg_robot/index.md).

**GMSL (Gigabit Multimedia Serial Link)** is a high-speed serial interface designed for transmitting uncompressed video, audio, and control data over long distances. It is commonly used in automotive applications for connecting cameras and other multimedia devices to the central processing unit.

GMSL supports data rates of up to 6 Gbps, allowing for high-resolution video transmission with low latency. It uses a differential signaling method to ensure signal integrity and reduce electromagnetic interference (EMI). GMSL also includes features such as error correction and power management to enhance reliability and efficiency.

In the context of robotics and autonomous mobile robots, GMSL sensors are often used for vision-based applications, such as object detection, lane keeping, and obstacle avoidance. These sensors can provide high-quality video feeds that are essential for the perception systems of autonomous vehicles.

When integrating GMSL sensors into a robotics system, it is important to consider factors such as compatibility with the processing unit, power requirements, and the physical layout of the system. Proper configuration and calibration of GMSL sensors are also crucial to ensure optimal performance and accurate data capture.

Intel® GMSL cameras use the Image Processor Unit (IPU) to process the video data captured by the camera. The IPU is responsible for tasks such as image enhancement, noise reduction, and color correction, which are essential for improving the quality of the video feed before it is used for further processing in the autonomous mobile robot's perception system.

It is crucial to understand the SerDes I2C connectivity specific to each ODM/OEM motherboard, Add-in-Card (AIC), and GMSL2 camera module. Illustrated below are the details a user needs to learn about I2C communication between a BDF (Bit-Definition File) Linux I2C adapter and GMSL2 I2C devices for Intel® Core™ Ultra Series 1 and 2 (Arrow Lake-U/H) and 12th/13th/14th Gen Intel® Core™ platforms to detect and configure GMSL capability. See [SerDes I2C mapping](./gmsl-guide/gmsl-aic-overview.md#how-to-detect-in-i2c-bus-to-gmsl2-deserializer-and-serializer-acpi-devices-mapping) for more details.

![GMSL overview](../images/gmsl/GMSL-overview2.png "gmsl overview")

## Next Steps

- [GMSL Add-in-Card Design Overview](./gmsl-guide/gmsl-aic-overview.md)
- [Configure Intel® GMSL `SerDes` ACPI Devices](./gmsl-guide/configure-gmsl-serdes-acpi.md)

<!--hide_directive
:::{toctree}
:hidden:

GMSL Add-in-Card Overview <./gmsl-guide/gmsl-aic-overview.md>
Configure GMSL SerDes ACPI Devices <./gmsl-guide/configure-gmsl-serdes-acpi.md>

:::
hide_directive-->
