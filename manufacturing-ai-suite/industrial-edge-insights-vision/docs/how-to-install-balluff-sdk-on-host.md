# Impact Acquire Installation and Setup Guide

The guide provides step-by-step instructions to install and configure the Balluff Impact Acquire software on a Linux system.

## 1. Create Python Virtual Environment
```bash
python -m venv camera-env
```

## 2. Install Required Packages
```bash
sudo apt update
sudo apt-get install -y libwxbase3.0-0v5 \
                        libwxbase3.0-dev \
                        libwxgtk3.0-gtk3-0v5 \
                        libwxgtk3.0-gtk3-dev \
                        libwxgtk-webview3.0-gtk3-0v5 \
                        libwxgtk-webview3.0-gtk3-dev \
                        wx3.0-headers \
                        libgtk2.0-dev
```

## 3. Download and Install Impact Acquire
```bash
cd ~/Downloads
wget https://assets-2.balluff.com/mvIMPACT_Acquire/3.6.0/ImpactAcquire-x86_64-linux-3.6.0.sh
chmod a+x ImpactAcquire-x86_64-linux-3.6.0.sh
./ImpactAcquire-x86_64-linux-3.6.0.sh
```

## 4. Optimize USB Performance
Edit GRUB configuration:
```bash
sudo nano /etc/default/grub
```
Add the following line:
```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb=256"
```
Then update GRUB:
```bash
sudo update-grub
```

## 5. Modify udev Configuration
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

## 6. Test Applications

### Single Capture Storage
```bash
cd /opt/ImpactAcquire/apps/SingleCapture/x86_64
./SingleCaptureStorage
```

### Common Settings Usage
```bash
cd /opt/ImpactAcquire/apps/GenICamCommonSettingsUsage/x86_64
./GenICamCommonSettingsUsage
```

## 7. Launch Impact Acquire GUI
```bash
cd /opt/ImpactAcquire/apps/ImpactControlCenter/x86_64
./ImpactControlCenter
```

When the GUI opens:
- Click **Action → Use Device**
- Choose **mvBlueFOX3**

---

**Reference:**
[Balluff Impact Acquire Quick Start Guide](https://assets.balluff.com/documents/DRF_957345_AA_000/mvBC_page_quickstart.html)
