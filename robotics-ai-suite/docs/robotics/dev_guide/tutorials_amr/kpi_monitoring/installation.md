<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Installation Guide

## 1. Set Up ROS2

Follow the [Getting Started guide](../../gsg_robot/index.md) to install and
configure ROS2 before continuing.

## 2. Install Simulation Packages

Follow the installation steps in each tutorial before running benchmarks:

- [Wandering AMR Simulation](../simulation/launch-wandering-application-gazebo-sim-waffle.md)
- [Pick & Place Simulation](../simulation/picknplace.md)

## 3. Install the KPI Monitoring Stack

Install `uv` (modern Python package manager):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

From the component root directory, install all dependencies:

```bash
make install
```

This installs system dependencies (`sysstat`), creates a `uv` virtual
environment with `--system-site-packages` access (required for ROS2), and
installs `matplotlib`, `numpy`, and `psutil`.

## 4. Set Up Passwordless SSH (Remote Monitoring)

Passwordless SSH is required when monitoring a ROS2 system on a remote machine
(e.g. a robot). Skip this step if you are monitoring locally.

```bash
# Generate a key on the monitoring machine (if needed)
ssh-keygen -t ed25519 -C "ros2-monitoring"

# Copy to the remote machine
ssh-copy-id username@remote-ip-address

# Verify
ssh username@remote-ip-address "echo 'SSH works!'"
```

Optional: add a host alias in `~/.ssh/config`:

```
Host robot
    HostName 192.168.1.100
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
```
