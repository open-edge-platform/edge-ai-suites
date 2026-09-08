# Conditional Setup

The guides below are conditional based on your hardware and software requirements.

| Guide | Condition | Description |
| --- | --- | --- |
| [Enabling Intel® Silicon on Ubuntu 22.04](#enabling-intel-graphics-on-ubuntu-2204) | You are running Ubuntu 22.04 and need to use Intel® GPU hardware. | Install a newer Linux kernel, firmware, and GPU drivers to enable Intel® silicon on Ubuntu 22.04. |
| [Enabling Real-time Linux kernel](#enabling-real-time-linux-kernel) | Your workload requires deterministic, low-latency real-time performance. | Install and boot a real-time Linux kernel for deterministic, low-latency performance. |
| [Enabling GMSL Cameras](#enabling-gmsl-cameras) | You are using cameras connected to the GMSL ports. | Configure ACPI tables and install drivers to use cameras connected to the GMSL ports. |

## Enabling Intel® Graphics on Ubuntu 22.04

If you are using an Intel® platform with Ubuntu 22
you may need to install an experimental Linux kernel, firmware, and GPU drivers for
development and deployment. Support for a custom Ubuntu 22 kernel and firmware is provided through Intel Edge Controls for Industrial (ECI). Driver support is provided through the third-party `kisak` PPA.

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

4. For latest Intel graphics support, add the Canonical ``kisak`` Private Package Archives (PPA):

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

## Enabling Real-time Linux kernel

Follow the [Real-time Linux](../../components/realtime_determinism/realtime_linux.md) guide for onboarding ECI, installing the kernel, and testing the real-time latency on your system.

## Enabling GMSL Cameras

GMSL on supported systems requires additional setup. See [GMSL Cameras](../../components/sensors/cameras/gmsl/index.md) for a step-by-step guide.
