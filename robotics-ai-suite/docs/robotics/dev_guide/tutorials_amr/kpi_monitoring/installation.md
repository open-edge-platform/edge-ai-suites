<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Installation Guide

## 1. Set Up ROS2

Follow the [Getting Started guide](../../../gsg_robot/index.md) to install and
configure ROS2 before continuing.

## 2. Install Simulation Packages

Follow the installation steps in each tutorial before running benchmarks:

- [Wandering AMR Simulation](../simulation/launch-wandering-application-gazebo-sim-waffle.md)
- [Pick & Place Simulation](../simulation/picknplace.md)

## 3. Install the KPI Monitoring Package

Install the benchmark framework package for your ROS distribution:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
sudo apt update
sudo apt install ros-jazzy-benchmark-framework
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
sudo apt update
sudo apt install ros-humble-benchmark-framework
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

This installs the KPI monitoring tools and all required system dependencies.

## 4. Install uv

[uv](https://docs.astral.sh/uv/) is used to manage Python dependencies:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your shell (or open a new terminal) so that `uv` is on your `PATH`.

From the benchmarking directory, install Python dependencies:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
cd /opt/ros/jazzy/benchmarking
uv sync
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
cd /opt/ros/humble/benchmarking
uv sync
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

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

```
Host robot
    HostName 192.168.1.100
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
```
