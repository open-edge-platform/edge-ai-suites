<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Installation Guide - ROS2 KPI Monitoring Stack

## Prerequisites

This monitoring stack requires:
1. **Python 3.8+** - For running the monitoring scripts
2. **uv** - Modern Python package manager (faster than pip)
3. **ROS2** - Required for monitoring ROS2 systems (local or remote)
4. **SSH access** - For remote monitoring (passwordless SSH keys recommended)

## Installation Steps

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Reload your shell or run:
source $HOME/.cargo/env
```

### 2. Install Python Dependencies

From the project root directory:

```bash
make install
```

This will:
- Install system dependencies (sysstat for resource monitoring)
- Create a virtual environment using uv
- Install Python packages: matplotlib, numpy, psutil
- Configure access to system site-packages (for ROS2)

Or manually:

```bash
# The uv virtual environment is already created with system-site-packages access
uv sync
```

### 3. Install ROS2 (Required for Graph Monitoring)

The monitoring stack needs ROS2 to connect to and monitor ROS2 systems.

#### Ubuntu 22.04 (Humble)

```bash
# Add ROS2 apt repository
sudo apt update && sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install -y curl gnupg lsb-release

sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
    http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | \
    sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Humble
sudo apt update
sudo apt install -y ros-humble-ros-base python3-rosdep

# Initialize rosdep
sudo rosdep init
rosdep update
```

### 4. Source ROS2 Environment

Add to your `~/.bashrc` to automatically source ROS2:

```bash
# Add this line to ~/.bashrc
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=0" >> ~/.bashrc

# Or source it now for the current session:
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
```

**Important**: Make sure `ROS_DOMAIN_ID` matches between the monitoring machine and the target system!

### 5. Verify Installation

```bash
# Check Python modules
uv run python -c "import matplotlib, numpy, psutil; print('✅ Python modules OK')"

# Check ROS2 (after sourcing)
source /opt/ros/humble/setup.bash
uv run python -c "import rclpy; print('✅ ROS2 (rclpy) OK')"

# Check system tools
which iostat && echo "✅ sysstat OK"
```

## Quick Start

After installation:

### Local Monitoring

```bash
# Source ROS2 environment first!
source /opt/ros/humble/setup.bash

# Run a quick check (30 seconds)
make quick-check

# Full monitoring (60 seconds)
make monitor

# Monitor specific node
make monitor-node NODE=/slam_toolbox
```

### Remote Monitoring

For monitoring a ROS2 system running on another machine:

1. **Set up SSH keys** (passwordless authentication):
   ```bash
   ssh-keygen -t ed25519
   ssh-copy-id user@remote-host
   ```

2. **Ensure ROS_DOMAIN_ID matches**:
   ```bash
   export ROS_DOMAIN_ID=0  # Must match on both machines
   ```

3. **Run remote monitoring**:
   ```bash
   source /opt/ros/humble/setup.bash
   make monitor-remote REMOTE_IP=10.34.94.191 REMOTE_USER=intel
   ```

## Remote Monitoring Setup Guide

This section covers the complete setup for monitoring ROS2 systems running on remote machines.

### Prerequisites

**On the monitoring machine (where you run this tool):**
- ROS2 installed and sourced
- This monitoring stack installed (`make install`)
- Network connectivity to the remote machine
- SSH client configured

**On the remote/target machine (system being monitored):**
- ROS2 system running
- SSH server enabled (`sudo apt install openssh-server`)
- User account with permissions to run ROS2 commands
- `pidstat` installed (`sudo apt install sysstat`)

### Network Configuration

The monitoring stack uses two communication channels:

1. **DDS Discovery** (UDP multicast/unicast) - For ROS2 topic/node discovery
2. **SSH** - For remote resource monitoring (CPU, memory, threads)

#### DDS Discovery Setup

ROS2 uses DDS for communication. For cross-machine discovery:

**Option 1: Same Local Network (easiest)**
```bash
# On both machines
export ROS_DOMAIN_ID=0  # Use same domain ID (0-101)
export ROS_LOCALHOST_ONLY=0  # Allow network discovery
```

**Option 2: Different Networks (requires explicit peers)**
```bash
# On monitoring machine
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/path/to/fastdds_profile.xml
```

Example `fastdds_profile.xml`:
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
    <participant profile_name="participant_profile" is_default_profile="true">
        <rtps>
            <builtin>
                <discovery_config>
                    <ignoreParticipantFlags>FILTER_DIFFERENT_PROCESS</ignoreParticipantFlags>
                    <initialPeersList>
                        <locator>
                            <udpv4>
                                <address>REMOTE_IP_ADDRESS</address>
                            </udpv4>
                        </locator>
                    </initialPeersList>
                </discovery_config>
            </builtin>
        </rtps>
    </participant>
</profiles>
```

### SSH Authentication Setup

**Step 1: Generate SSH key (if you don't have one)**
```bash
# On monitoring machine
ssh-keygen -t ed25519 -C "ros2-monitoring"
# Press Enter to accept default location (~/.ssh/id_ed25519)
# Optionally set a passphrase (recommended for security)
```

**Step 2: Copy key to remote machine**
```bash
ssh-copy-id username@remote-ip-address

# Example:
ssh-copy-id ubuntu@192.168.1.100
ssh-copy-id intel@10.34.94.191
```

**Step 3: Test SSH connection**
```bash
ssh username@remote-ip-address "echo 'SSH works!'"

# Should not prompt for password if keys are set up correctly
```

**Step 4: (Optional) Configure SSH for convenience**

Edit `~/.ssh/config`:
```
Host robot
    HostName 192.168.1.100
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
    
Host jetson
    HostName 10.34.94.191
    User intel
    IdentityFile ~/.ssh/id_ed25519
```

Now you can use: `ssh robot` instead of `ssh ubuntu@192.168.1.100`

### Environment Synchronization

**Critical**: Both machines must use the same ROS_DOMAIN_ID!

**On monitoring machine:**
```bash
export ROS_DOMAIN_ID=0
source /opt/ros/humble/setup.bash
```

**On remote/target machine:**
```bash
export ROS_DOMAIN_ID=0
source /opt/ros/humble/setup.bash
# Start your ROS2 application
```

**Make it permanent** (add to `~/.bashrc` on both machines):
```bash
echo "export ROS_DOMAIN_ID=0" >> ~/.bashrc
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### Firewall Configuration

If you have firewall enabled, you need to allow DDS traffic.

**On both machines (Ubuntu with ufw):**
```bash
# Allow DDS multicast discovery (port 7400)
sudo ufw allow 7400/udp

# Allow DDS unicast communication (ports 7410-7610)
sudo ufw allow 7410:7610/udp

# Allow SSH (if not already allowed)
sudo ufw allow 22/tcp

# Reload firewall
sudo ufw reload
```

**For more restrictive setup** (only allow specific IP):
```bash
# On remote machine, only allow monitoring machine
sudo ufw allow from MONITORING_IP to any port 7400:7610 proto udp
```

### Testing Remote Connectivity

**Step 1: Verify network connectivity**
```bash
ping remote-ip-address
```

**Step 2: Verify SSH access**
```bash
ssh username@remote-ip "uptime"
```

**Step 3: Verify ROS2 topic visibility**
```bash
# On remote machine: start a simple talker
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
ros2 run demo_nodes_cpp talker

# On monitoring machine: check if you can see topics
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
ros2 topic list
# Should see /chatter if DDS discovery works
```

**Step 4: Use the dependency checker**
```bash
# Comprehensive check including remote connectivity
make check-deps REMOTE_IP=192.168.1.100 REMOTE_USER=ubuntu
```

### Running Remote Monitoring

Once setup is complete:

**Full remote monitoring (with thread details):**
```bash
make monitor-remote REMOTE_IP=192.168.1.100 REMOTE_USER=ubuntu DURATION=120
```

**Remote monitoring (PID-only mode, less overhead):**
```bash
make monitor-remote-pid REMOTE_IP=192.168.1.100 REMOTE_USER=ubuntu DURATION=120
```

**Monitor specific node remotely:**
```bash
make monitor-remote REMOTE_IP=192.168.1.100 NODE=/slam_toolbox DURATION=180
```

**Using hostname from SSH config:**
```bash
# If you configured ~/.ssh/config with Host "robot"
make monitor-remote REMOTE_IP=robot REMOTE_USER=ubuntu
```

### Troubleshooting Remote Monitoring

#### Cannot see remote ROS2 topics

**Check 1: ROS_DOMAIN_ID mismatch**
```bash
# On both machines
echo $ROS_DOMAIN_ID
# Must be the same!
```

**Check 2: ROS_LOCALHOST_ONLY is set**
```bash
echo $ROS_LOCALHOST_ONLY
# Should be 0 or unset for network communication
```

**Check 3: Firewall blocking DDS**
```bash
# Temporarily disable firewall for testing
sudo ufw disable
# Try monitoring again
# If it works, configure firewall properly (see above)
```

**Check 4: Different ROS2 distributions**
```bash
# On both machines
echo $ROS_DISTRO
# Should be compatible (e.g., both Humble, or Humble + Iron)
```

#### SSH connection fails

**Check 1: SSH service running on remote**
```bash
ssh username@remote-ip
# If this prompts for password, keys aren't set up
```

**Check 2: Permissions on SSH keys**
```bash
# On monitoring machine
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub

# On remote machine
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

**Check 3: SSH agent** (if using passphrase)
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

#### High network latency or packet loss

```bash
# Check latency
ping -c 10 remote-ip

# Monitor in shorter intervals to reduce data
make monitor-remote REMOTE_IP=remote-ip INTERVAL=10 DURATION=60

# Use PID-only mode (less SSH traffic)
make monitor-remote-pid REMOTE_IP=remote-ip
```

#### Resource monitoring works but no graph data

This means SSH is working but DDS discovery is not. See "Cannot see remote ROS2 topics" above.

#### Graph monitoring works but no resource data

**Check: pidstat available on remote**
```bash
ssh username@remote-ip "which pidstat"
# If not found:
ssh username@remote-ip "sudo apt install -y sysstat"
```

## Using the Setup Script

A convenience script is provided to source ROS2:

```bash
# Source ROS2 and set up environment
source ./setup_ros2_env.sh

# Now run monitoring commands
make monitor-remote REMOTE_IP=10.34.94.191 REMOTE_USER=intel
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'rclpy'"

**Solution**: ROS2 is not sourced or not installed.

```bash
# Check if ROS2 is installed
ls /opt/ros/

# Source ROS2
source /opt/ros/humble/setup.bash

# Add to ~/.bashrc to make permanent
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### "ModuleNotFoundError: No module named 'matplotlib'"

**Solution**: Python modules not installed in virtual environment.

```bash
# Install/sync dependencies
uv sync

# Or use make install
make install
```

### Remote Monitoring Connection Issues

**Solution**: Check network connectivity and ROS_DOMAIN_ID.

```bash
# Test SSH connection
ssh user@remote-host

# Check ROS_DOMAIN_ID matches
echo $ROS_DOMAIN_ID  # On both machines

# Test ROS2 topics visibility (when remote system is running)
source /opt/ros/humble/setup.bash
ros2 topic list  # Should see remote topics
```

### Permission Denied for SSH

**Solution**: Set up SSH keys or provide password when prompted.

```bash
# Generate SSH key
ssh-keygen -t ed25519

# Copy to remote host
ssh-copy-id user@remote-host

# Test
ssh user@remote-host "echo 'SSH works!'"
```

## Environment Variables

Key environment variables:

- `ROS_DOMAIN_ID` - Must match between monitoring and target systems (default: 0)
- `ROS_LOCALHOST_ONLY` - Set to 1 for local-only ROS2 communication
- `RMW_IMPLEMENTATION` - ROS2 middleware (usually auto-detected)

## Next Steps

After successful installation:

1. Read [QUICK_START.md](docs/QUICK_START.md) for usage examples
2. Check [COMMANDS.md](docs/COMMANDS.md) for all available commands
3. See [examples/](examples/) for common monitoring scenarios

## Summary

Complete installation command sequence:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
make install

# Install ROS2 (Ubuntu 22.04)
sudo apt install -y ros-humble-ros-base

# Set up environment
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=0" >> ~/.bashrc
source ~/.bashrc

# Verify
./setup_ros2_env.sh
make quick-check
```
