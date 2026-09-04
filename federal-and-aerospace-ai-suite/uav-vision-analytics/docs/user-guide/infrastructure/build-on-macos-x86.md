<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Build Artifacts on macOS (x86 VM)

This guide walks you through running the Phase 1 build on a **macOS** machine (any chip)
using a Ubuntu 24.04 x86_64 virtual machine in UTM.

> The build scripts require Linux. macOS is not directly supported.
> This guide uses UTM (free) with Ubuntu 24.04 Desktop x86_64 as the build environment.

> **Performance note:** On Apple Silicon Macs, UTM runs x86_64 VMs via QEMU software
> emulation (TCG) — there is no KVM hardware acceleration for x86 on ARM hosts.
> The build will complete correctly but will be **3–5× slower** than on native x86
> hardware. On Intel Macs, QEMU can use HVF acceleration and runs at near-native speed.

---

## Prerequisites

| What | Where |
|------|-------|
| macBook (any chip — Apple Silicon or Intel) | — |
| macOS Ventura or later | — |
| UTM (free VM app) | https://mac.getutm.app |
| Ubuntu 24.04 **Server** amd64 ISO | https://releases.ubuntu.com/24.04/ |
| 64 GB free disk space | For VM + build output |
| 12 GB RAM free | 8 GB assigned to VM minimum |

---

## Step 1 — Install UTM

1. Go to **https://mac.getutm.app** and click **Download**.
2. Open the downloaded `.dmg` and drag **UTM** to your Applications folder.
3. Open UTM. If macOS blocks it: right-click → **Open** → **Open** again.

---

## Step 2 — Download Ubuntu 24.04 Server amd64

Download the **Server amd64 ISO** from the Ubuntu releases page:

```
https://releases.ubuntu.com/noble/ubuntu-24.04.4-live-server-amd64.iso
```

File: `ubuntu-24.04.4-live-server-amd64.iso` (3.2 GB)

> Use the **server** ISO — the build runs entirely in a terminal inside Docker
> containers. No desktop environment is needed, and the server ISO is half the
> size and installs in roughly a third of the time.

---

## Step 3 — Create the Ubuntu VM in UTM

1. Open UTM → click **Create a New Virtual Machine**.
2. Select **Emulate** (not Virtualize — x86_64 emulation is required on Apple Silicon;
   on Intel Mac you may use Virtualize with HVF for better performance).
3. Select **Linux**.
4. Under **Boot ISO Image** → Browse → select the amd64 ISO you downloaded.
5. Set:
   - **Architecture**: x86_64
   - **RAM**: 8192 MB
   - **CPU cores**: 12
   - **Storage**: 64 GB
6. Click **Save**.

---

## Step 4 — Install Ubuntu in the VM

1. Click **▶ Play** in UTM to start the VM.
2. Follow the text-based server installer — accept defaults for everything except:
   - Set a username and password you will remember.
   - On the storage screen confirm **Use entire disk**.
   - On the profile screen set your name, server name, username, and password.
3. When prompted, select **Install OpenSSH server** (optional but useful).
4. Let the install complete (~8–12 min under emulation) and reboot into the VM.
5. Log in with your username and password at the terminal prompt.

---

## Step 5 — Install Prerequisites Inside the VM

Open a terminal inside the Ubuntu VM.

### Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Allow your user to run docker without sudo
sudo usermod -aG docker $USER
newgrp docker
```

Verify:

```bash
docker run --rm hello-world
```

### Make and Git

```bash
sudo apt install -y make git
```

---

## Step 6 — Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-node-infrastructure-blueprint.git
cd edge-node-infrastructure-blueprint
```

---

## Step 7 — Configure Proxy (corporate networks only)

If your network requires a proxy, edit `proxy.env` in the repo root:

```bash
nano proxy.env
```

Fill in:

```
HTTP_PROXY="http://proxy.mycompany.com:8080"
HTTPS_PROXY="http://proxy.mycompany.com:8080"
NO_PROXY="localhost,127.0.0.0/8"
http_proxy="http://proxy.mycompany.com:8080"
https_proxy="http://proxy.mycompany.com:8080"
no_proxy="localhost,127.0.0.0/8"
```

On a home or open network, leave all values empty — the build will prompt and
you can confirm to proceed without a proxy.

---

## Step 8 — Build the USB Artifacts

Run from the repository root inside the VM:

```bash
make build
```

This is equivalent to `make build MODE=standard-image`. No extra flags are required —
the VM is native x86_64 so all Docker images build and run correctly without any
cross-compilation or QEMU user-static setup.

The first build downloads base images, installs packages, and assembles the USB
artifacts. Expected duration:

| Mac type | Estimated build time |
|---|---|
| Apple Silicon (QEMU TCG emulation) | 2–3 hours |
| Intel Mac (HVF acceleration) | 15–30 minutes |

> **Total end-to-end time on Apple Silicon** (UTM setup + Ubuntu install + build):
> approximately **2–3 hours** for a first-time run after the VM is already set up,
> or **4–5 hours** including VM creation and Ubuntu installation.

Build output appears at:

```
infrastructure/build-artifacts/out/usb-installation-files.tar.gz
```

---

## Step 9 — Prepare the Bootable USB

Plug your USB drive into the Mac. In UTM, pass it through to the VM:

1. With the VM running, click the **USB icon** in the UTM toolbar.
2. Select your USB drive from the list to pass it through to the VM.

Inside the VM, identify the USB device:

```bash
lsblk
```

Look for a device like `/dev/sda` or `/dev/sdb` with the USB's capacity.

Extract the build output and run the USB preparation script:

```bash
cd infrastructure/build-artifacts/out

sudo tar -xzf usb-installation-files.tar.gz

# Replace /dev/sdX with your actual USB device from lsblk
sudo ./bootable-usb-prepare.sh /dev/sdX usb-bootable-files.tar.gz config-file
```

> **Double-check the device path** — this will erase the target device.

After the script completes:

1. In UTM, click the USB icon and disconnect the drive from the VM.
2. Safely eject it from macOS.
3. Connect the USB to the target edge node.
4. Enter the BIOS/UEFI boot menu and boot from the USB.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot run docker without sudo` | User not in `docker` group | `sudo usermod -aG docker $USER && newgrp docker` |
| `docker pull` fails / timeout | Proxy not configured | Fill in `proxy.env` before running `make build` |
| VM very slow / unresponsive | QEMU TCG on Apple Silicon | Reduce VM RAM to free host memory; close other apps; increase VM CPU cores |
| UTM VM freezes during Docker build | Insufficient disk | Ensure VM disk is ≥ 64 GB; delete old Docker images with `docker system prune` |
| USB device not visible in VM | Not passed through UTM | Click USB icon in UTM toolbar → select the drive |
| Build fails on Intel Mac with `KVM not available` | HVF not enabled | In UTM VM settings → CPU → enable **Force Multicore** and set **Architecture** to x86_64 |
