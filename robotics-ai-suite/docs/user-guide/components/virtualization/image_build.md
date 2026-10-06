# Build Ubuntu Image

This guide explains how to build a `qcow2` virtual disk image from an Ubuntu 24.04 ISO using QEMU/KVM.

## Prerequisites

1. Host packages installed:

   ```bash
   sudo apt update
   sudo apt install -y qemu-system-x86 qemu-utils ovmf
   ```

2. Ubuntu 24.04 ISO downloaded, [ubuntu iso download](https://releases.ubuntu.com/), select ubuntu 24.04 desktop image, for example:

   - `$HOME/ubuntu-24.04.4-desktop-amd64.iso`

## Create a qcow2 Disk

Create a 128 GiB image file (adjust size as needed):

```bash
mkdir -p "$HOME/vm-images"
qemu-img create -f qcow2 "$HOME/vm-images/ubuntu24.04.qcow2" 128G
```

Check image information:

```bash
qemu-img info "$HOME/vm-images/ubuntu24.04.qcow2"
```

## Install Ubuntu 24.04 into the qcow2 Image

Boot the ISO installer and install the OS into the qcow2 disk:

```bash
qemu-system-x86_64 \
  -enable-kvm \
  -machine q35 \
  -cpu host \
  -smp 4 \
  -m 4G \
  -bios /usr/share/ovmf/OVMF.fd \
  -drive file="$HOME/vm-images/ubuntu24.04.qcow2",if=virtio,format=qcow2,cache=none \
  -cdrom "$HOME/ubuntu-24.04.4-desktop-amd64.iso" \
  -boot d \
  -netdev user,id=net0 \
  -device virtio-net-pci,netdev=net0 \
  -display gtk
```
then select `Install Ubuntu` to continue normal ubuntu image install process. After install process, ubuntu24.04.qcow2 is ready for use.
