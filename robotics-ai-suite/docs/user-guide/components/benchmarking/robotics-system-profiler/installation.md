<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Installation Guide

## 1. Set Up ROS2

Follow the [Getting Started](../../../platform_foundation/getting_started.md) guide to install and
configure ROS2 before continuing.

## 2. Install Simulation Packages

Follow the installation steps in each tutorial before running benchmarks:

- [Wandering AMR Simulation](../../../software_references/amr/simulation/wandering_sim.md)
- [Pick & Place Simulation](../../middleware/gazebo/reference_applications/picknplace.md)

## 3. Install the Robotics System Profiler Package

Install the Robotics System Profiler package for your ROS distribution:

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
sudo apt update
sudo apt install ros-jazzy-benchmark-framework
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
sudo apt update
sudo apt install ros-humble-benchmark-framework
```

:::
::::

This installs the Robotics System Profiler tools and all required system dependencies.

## 4. Install uv

[uv](https://docs.astral.sh/uv/) is used to manage Python dependencies:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your shell (or open a new terminal) so that `uv` is on your `PATH`.

From the benchmarking directory, install Python dependencies:

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
cd /opt/ros/jazzy/benchmarking
uv sync
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
cd /opt/ros/humble/benchmarking
uv sync
```

:::
::::

## 5. Set Up Passwordless SSH (Remote Monitoring)

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

```text
Host robot
    HostName 192.168.1.100
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
```
