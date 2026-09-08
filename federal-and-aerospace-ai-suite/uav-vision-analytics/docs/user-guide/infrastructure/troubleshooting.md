<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Troubleshooting

- Docker build fails: Recheck the Docker daemon and CLI proxy settings, then restart the Docker daemon.
- USB preparation fails: Verify the device path and available USB capacity.
- `kubectl` issues: Confirm that the Kubernetes installation has completed and the node status is `Ready`.
- GPU or NPU not detected: Inspect `dmesg` for driver load failures.
- After a successful OS provisioning reboot, if the edge node boots from USB and starts provisioning again, the Boot Override option is enabled in the target system BIOS. Disable Boot Override, or ensure USB is not the first option in the Boot Override list. Set the hard disk as the default boot option, then save and exit.
- OS installation fails: Set `debug_mode=true` in the `config-file`, rebuild the USB, and reboot to enable **Debug Mode** with interactive prompts. Optionally, run `/usr/local/bin/os-install.sh -i` on the Alpine OS terminal to launch the installer in interactive debug mode.
