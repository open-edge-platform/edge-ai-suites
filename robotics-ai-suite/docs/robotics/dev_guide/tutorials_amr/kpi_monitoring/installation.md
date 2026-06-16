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

## 4. Set Up the Benchmarking Directory

Copy the installed package to a user-writable directory, then run
`make install` to install system dependencies and `uv`:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
cp -r /opt/ros/jazzy/benchmarking ~/ros-kpi
cd ~/ros-kpi
make install
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
cp -r /opt/ros/humble/benchmarking ~/ros-kpi
cd ~/ros-kpi
make install
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

`make install` installs system packages (`sysstat`, `python3-tk`) and `uv`.
Then install Python dependencies into a local virtual environment:

```bash
PATH="$HOME/.local/bin:$PATH" uv sync
sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg
```

 Reopen your terminal after `make install` so that `uv` is on your `PATH`.
```bash
cd ~/ros-kpi
```

## 5. Source Your ROS2 Environment

Before running any monitoring commands, source your ROS2 environment and set
`ROS_DOMAIN_ID` to match the system you want to monitor. Run these in every
terminal where you use the KPI tools:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=45   # must match the monitored system
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42   # must match the monitored system
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

> Add these lines to your `~/.bashrc` to avoid repeating them in every terminal.

## 6. Set Up Passwordless SSH (Remote Monitoring)

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
