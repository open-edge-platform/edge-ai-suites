# Pylon SDK Installation and Setup Guide

The guide provides step-by-step instructions to install and configure the Basler pylonviewer tool on a Linux system.

## 1. Download the SDK
Download the latest **Pylon SDK** (preferably the Debian installer) from the official Basler website:

- Go to: https://www.baslerweb.com/en/downloads/software/

## 2. Extract the Installer
After downloading the archive (example: `pylon-X.X_linux-x86_64_debs.tar.gz`), extract it:

```bash
tar -xvf pylon-X.X_linux-x86_64_debs.tar.gz
```

## 3. Install Dependencies
Install required dependencies:

```bash
sudo apt install libxcb-cursor0
```

## 4. Install Pylon SDK Packages
Install the `.deb` package:

```bash
sudo dpkg -i pylon_X.X-deb0_amd64.deb
```

## 5. Verify Additional Instructions
Refer to the **INSTALL** file included in the extracted SDK folder for any updated steps or additional notes.

## 6. Run the pylonviewer

```bash
/opt/pylon/bin/pylonviewer
```

## Troubleshooting

For Basler USB Cameras if you face issue with the detection of the camera, you can perform the following steps
```bash
sudo apt install v4l-utils
v4l2-ctl --list-devices
stat /dev/bus/usb
sudo usermod -a -G dialout $USER
# Run the USB setup script
/opt/pylon/share/pylon/setup-usb.sh
sudo reboot
```