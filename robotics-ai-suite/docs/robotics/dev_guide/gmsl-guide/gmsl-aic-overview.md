# GMSL Add-in-Card Design Overview

A GMSL product design based on Intel® Core™ Ultra Series 1 and 2 (Arrow Lake-U/H) or 12th/13th/14th Gen Intel® Core™ products can be illustrated as follows:

![GMSL overview architecture](../../images/gmsl/GMSL-overview.png "gmsl overview architecture")

- The **GMSL2 camera modules**, designed by third-party GMSL2 camera vendors, combine a camera sensor and GMSL2 serializer, for example `MAX9295`.
- The **Add-in-Card (AIC)**, designed by either ODM/OEMs or third-party GMSL2 camera vendors, provides multiple GMSL2 _deserializers_, for example `MAX9296A`.
- The **Intel®-based motherboard**, designed by ODM/OEMs, provides the Mobile Industry Processor Interface (MIPI) Camera Serial Interface (CSI) exposed by Intel® Core™ Ultra Series 1 and 2 (Arrow Lake-U/H) and 12th/13th/14th Gen Intel® Core™ products.

There are two design approaches for GMSL Add-in-Card (AIC):

- **Standalone-mode** `SerDes`: A single GMSL serializer, for example `MAX9295`, and camera sensor devices per deserializer, for example `MAX9296A`. One example is the [Axiomtek ROBOX500 4x GMSL camera interfaces](https://www.axiomtek.com/ROBOX500/) Add-in-Card (AIC).

  ![Standalone link example](../../images/gmsl/GMSL-standalone-D457_-csi-port0.png "standalone link example")

- **Aggregated-link** `SerDes`: Dual GMSL serializers, for example `MAX9295`, and camera sensor devices per deserializer, for example `MAX9296A`. Examples include the [Axiomtek ROBOX500 8x GMSL camera interfaces](https://www.axiomtek.com/ROBOX500/), the [Advantech GMSL Input Module Card](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/mioe-gmsl/mod_fc1fc070-30f8-40c1-881f-56c967e26924) for [AFE-R360 series](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/afe-r360/mod_1e4a1980-9a31-46e6-87b6-affbd7a2cb44) or [ASR-A502 series](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/asr-a502/mod_ccca0f36-a50b-40c7-87b7-10fb96448605), and the [SEAVO Embedded Computer HB03](https://www.seavo.com/en/products/products-info_itemid_693.html) Add-in-Cards (AIC).

  ![Aggregated link example](../../images/gmsl/GMSL-aggregated-D457_csi-port0.png "aggregated link example")

  It is crucial to understand the `SerDes` I2C connectivity specific to each ODM/OEM motherboard, Add-in-Card (AIC), and GMSL2 camera module. Illustrated below are all details a user needs to learn about I2C communication between a BDF (Bit-Definition File) Linux I2C adapter and GMSL2 I2C devices for Intel® Core™ Ultra Series 1 and 2 (Arrow Lake-U/H) and 12th/13th/14th Gen Intel® Core™ platforms to detect and configure GMSL capability. See [SerDes I2C mapping](#how-to-detect-in-i2c-bus-to-gmsl2-deserializer-and-serializer-acpi-devices-mapping) for further details.

  ![SerDes I2C mapping overview](../../images/gmsl/GMSL-overview2.png "serdes i2c mapping overview")

  More details are available in the [Mobile Industry Processor Interface (MIPI) Camera Serial Interface (CSI) Gigabit Multimedia Serial Link (GMSL) Add-in Card (AIC) Schematic](https://cdrdv2.intel.com/v1/dl/getContent/814789?explicitVersion=true).

## How To Detect in I2C Bus to GMSL2 _Deserializer_ and _Serializer_ ACPI Devices Mapping

The best way to detect I2C bus to GMSL2 _Deserializer_ and _Serializer_ ACPI devices mapping is by using the `i2cdetect` command-line tool from the `i2c-tools` package on Linux.

```bash
i2cdetect -y <i2c_bus_number>
```

Here, `<i2c_bus_number>` is the I2C bus number assigned to GMSL2 _Deserializer_ and _Serializer_ ACPI devices.

Below is an example output from `i2cdetect` for GMSL2 _Deserializer_ and _Serializer_ ACPI devices mapping:

```console
i2cdetect -r -y 0 0x20 0x6f
       0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
  00:
  10:             -- -- -- -- -- -- 1a -- -- -- -- --
  20: -- -- -- -- -- -- -- 27 -- -- -- -- -- -- -- --
  30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  50: -- -- -- -- 54 -- -- -- -- -- -- -- 5c -- -- --
  60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  70:
```

```console
i2cdetect -r -y 1 0x20 0x6f
      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
  00:
  10:             -- -- -- -- -- -- -- -- -- -- -- --
  20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  70:
```

As you can see, the sample devices are on I2C bus `0` at addresses `0x1a`, `0x27`, `0x40`, and `0x54`, corresponding to the GMSL2 _Deserializer_ and _Serializer_ ACPI devices configured on the system.

## GMSL2 Driver

Prerequisites for the GMSL driver can be found in the ECI APT repository.

Follow the [Set up ECI APT Repository](https://eci.intel.com/docs/3.3/getstarted/download_eci.html#setupecirepo) guide first.

Once the ECI APT repository is set up, install the GMSL driver with:

```bash
sudo apt-get update
sudo apt-get install intel-mipi-gmsl-dkms
```

Select the `max929x` or `max967xx` deserializer to compile the required Linux V4L2 I2C sensor driver.

Reboot the system and enter BIOS/UEFI settings. Navigate to the ACPI configuration section and verify that the GMSL SerDes device is listed and enabled. If it is not present, update the system firmware or consult the hardware vendor.

Go into UEFI Advanced settings.

![UEFI advanced](../../images/gmsl/UEFI-Advanced.png "uefi advanced settings")

Navigate to System Agent (SA).

![UEFI system agent](../../images/gmsl/UEFI-SA.png "uefi system agent")

Navigate to MIPI Configuration.

![UEFI MIPI configuration](../../images/gmsl/UEFI-MIPI-Config.png "uefi mipi configuration")

Ensure GMSL SerDes is enabled.

![Enable camera](../../images/gmsl/UEFI-Enable-Camera.png "enable gmsl serdes")

After enabling the GMSL SerDes device in UEFI, click `link options` to adjust the settings for the GMSL SerDes link.

Boot the system into the OS.
