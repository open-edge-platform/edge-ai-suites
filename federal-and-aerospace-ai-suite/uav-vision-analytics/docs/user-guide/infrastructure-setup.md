<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Infrastructure Setup

Covers building the OS image, flashing it to a bootable USB, and validating the provisioned platform for the Uncrewed Aerial Vehicle Blueprint.

> **Note**: The full installation guide for the Edge Node Infrastructure Software is available at
> [Edge-Node Infrastructure Software — Open Edge Platform Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/index.html).

## Step 1: Clone the repository

```bash
git clone https://github.com/open-edge-platform/edge-node-infrastructure-blueprint.git -b main
cd edge-node-infrastructure-blueprint
```

> **Note:** If your development environment is behind a firewall, add proxy settings to `proxy.env` in the repository root before building. To skip proxy entirely, pass `skip-proxy=true` to `make`.

## Step 2: Build the OS image

Export credentials and run the server-oriented UAV build:

```bash
export USERNAME='<your-username>'
export PASSWORD="$(openssl passwd -6 '<your-password>')"
make build MODE=server-image
```

**Output:** `infrastructure/build-artifacts/out/usb-installation-files.tar.gz`

> For a customized UAV image using the Image Composer Tool, see
> [Advanced Image Customization](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/advanced-image-customization.html) and use the
> UAV companion OS template: `infrastructure/host-os/ict/work-generic-companion-os-server-template.yml`

## Step 3: Prepare the bootable USB

On the developer system, extract the artifacts:

```bash
sudo tar -xzf usb-installation-files.tar.gz
```

Extracted files: `usb-bootable-files.tar.gz`, `config-file`, `bootable-usb-prepare.sh`, `ven-deployment.sh`.

Edit `config-file` and set:

- `ssh_key` — SSH public key for passwordless access to the target
- `host_type` — `container` (default) or `kubernetes`
- `SRIOV` — enable or disable SR-IOV
- Proxy values — if required on your network

Identify the USB device with `lsblk`, then flash:

```bash
# Replace /dev/sdX with the correct USB device
sudo ./bootable-usb-prepare.sh /dev/sdX usb-bootable-files.tar.gz config-file
```

Safely disconnect the USB, attach it to the target system, and boot from USB. The OS installs automatically without any user intervention.

## Step 4: Validate post-boot bring-up

After first-boot provisioning completes, verify services on the target system.

For container mode (`host_type=container`, default):

```bash
docker info
docker ps
```

For Kubernetes mode (`host_type=kubernetes`):

```bash
sudo kubectl get nodes
sudo kubectl get pods -A
```

Expected pods include:

```text
intel-device-plugins     intel-gpu-plugin-xxxxx    1/1   Running
intel-device-plugins     intel-npu-plugin-xxxxx    1/1   Running
node-feature-discovery   nfd-master-xxxxx          1/1   Running
node-feature-discovery   nfd-worker-xxxxx          1/1   Running
```

Verify SR-IOV and driver bring-up:

```bash
sudo cat /sys/kernel/debug/dri/0000:00:02.1/sriov_info
sudo dmesg | grep xe
sudo dmesg | grep vpu
```
<!--hide_directive
:::{toctree}
:hidden:

System Requirements <./get-started/system-requirements.md>
Advanced Image Customization <./infrastructure/advanced-image-customization.md>
Build on macOS (x86 VM) <./infrastructure/build-on-macos-x86.md>
Infrastructure Capabilities <./infrastructure/platform-capabilities.md>
Troubleshooting <./infrastructure/troubleshooting.md>

:::
hide_directive-->
