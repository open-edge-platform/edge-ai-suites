# Impact Acquire Installation and Setup Guide

The guide provides step-by-step instructions to install and configure the Balluff Impact Acquire software on a Linux system.

## 1. Install Required Packages

```bash
sudo apt update
sudo apt-get install -y libwxbase3.2-1 \
                        libwxgtk3.2-dev \
                        libwxgtk-webview3.2-dev \
                        wx3.2-headers \
                        libexpat1-dev
```

## 2. Download and Install Impact Acquire

```bash
cd ~/Downloads
wget https://assets-2.balluff.com/mvIMPACT_Acquire/3.7.0/ImpactAcquire-x86_64-linux-3.7.0.sh
chmod a+x ImpactAcquire-x86_64-linux-3.7.0.sh
./ImpactAcquire-x86_64-linux-3.7.0.sh
```

## 3. Optimize USB Performance

Edit GRUB configuration:

```bash
sudo nano /etc/default/grub
```

Add the following line:

```text
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb=256"
```

Then update GRUB:

```bash
sudo update-grub
```

## 4. Modify udev Configuration

Edit the file:

```bash
sudo nano /etc/init.d/udev
```

Comment out the following lines:

```bash
#if [ ! -w /sys ]; then
#    log_warning_msg "udev does not support containers, not started"
#    exit 0
#fi
```

## 5. Test Applications

### Single Capture Storage

```bash
cd /opt/ImpactAcquire/apps/SingleCapture/x86_64
./SingleCapture
```

### Common Settings Usage

```bash
cd /opt/ImpactAcquire/apps/GenICamCommonSettingsUsage/x86_64
./GenICamCommonSettingsUsage
```

## 6. Launch Impact Acquire GUI

```bash
cd /opt/ImpactAcquire/apps/ImpactControlCenter/x86_64
./ImpactControlCenter
```

When the GUI opens:

- Click **Action → Use Device**
- Choose **mvBlueFOX3**

## Troubleshooting

### ImpactControlCenter GUI Does Not Open

If the GUI fails to launch, force it to use the X11 backend:

```bash
GDK_BACKEND=x11 ./ImpactControlCenter
```

## References

- [Balluff Impact Acquire Quick Start Guide](https://assets.balluff.com/documents/DRF_957345_AA_000/mvBC_page_quickstart.html)
