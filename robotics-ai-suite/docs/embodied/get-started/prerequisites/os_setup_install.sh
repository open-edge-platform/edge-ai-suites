#!/usr/bin/env bash
#
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

print_usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options]

Automates the software steps from docs/embodied/get-started/prerequisites/os_setup.rst
and its included pages (locale + APT repositories).

Options:
  --set-date "YYYY-MM-DD HH:MM"   Set system date/time via: date -s
  --disable-auto-upgrades          Disable Ubuntu auto-upgrade settings
  --fix-raw-github-host            Add 185.199.108.133 raw.githubusercontent.com to /etc/hosts
  -h, --help                       Show this help message

Notes:
  - Ubuntu installation and BIOS setup are manual and cannot be automated by script.
  - Script is designed for Ubuntu 22.04 Desktop and requires sudo/root.
EOF
}

SET_DATE=""
DISABLE_AUTO_UPGRADES=false
FIX_RAW_GITHUB_HOST=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --set-date)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --set-date" >&2; exit 1; }
      SET_DATE="$1"
      ;;
    --disable-auto-upgrades)
      DISABLE_AUTO_UPGRADES=true
      ;;
    --fix-raw-github-host)
      FIX_RAW_GITHUB_HOST=true
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_usage
      exit 1
      ;;
  esac
  shift
done

log() {
  echo "[os-setup] $*"
}

run_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

log "Manual prerequisites from guide:"
log "1) Install Ubuntu 22.04 Desktop (64-bit)"
log "2) Configure BIOS according to bios-generic.rst"

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "22.04" ]]; then
    log "Warning: detected ${PRETTY_NAME:-unknown}. Guide targets Ubuntu 22.04 Desktop."
  else
    log "Detected supported OS: ${PRETTY_NAME}"
  fi
fi

require_cmd apt
require_cmd dpkg
require_cmd tee

log "Setting locale prerequisites"
run_sudo apt update
run_sudo apt install -y locales wget software-properties-common curl gnupg
run_sudo locale-gen en_US en_US.UTF-8
run_sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

if [[ -n "$SET_DATE" ]]; then
  log "Setting date/time to: $SET_DATE"
  run_sudo date -s "$SET_DATE"
else
  log "Current date/time: $(date)"
  log "Skip setting date/time (use --set-date to configure it)"
fi

log "Configuring Intel ECI APT repository key"
run_sudo mkdir -p /usr/share/keyrings
run_sudo wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | run_sudo tee /usr/share/keyrings/eci-archive-keyring.gpg >/dev/null

log "Configuring Intel ECI APT repository list"
ECI_CODENAME="$(source /etc/os-release && echo "$VERSION_CODENAME")"
run_sudo tee /etc/apt/sources.list.d/eci.list >/dev/null <<EOF
deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${ECI_CODENAME} isar main
deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${ECI_CODENAME} isar main
EOF

if [[ "$DISABLE_AUTO_UPGRADES" == true ]]; then
  log "Disabling auto-upgrades in /etc/apt/apt.conf.d/20auto-upgrades"
  run_sudo sed -i 's/APT::Periodic::Update-Package-Lists "1"/APT::Periodic::Update-Package-Lists "0"/g' /etc/apt/apt.conf.d/20auto-upgrades || true
  run_sudo sed -i 's/APT::Periodic::Unattended-Upgrade "1"/APT::Unattended-Upgrade "0"/g' /etc/apt/apt.conf.d/20auto-upgrades || true
fi

log "Configuring APT pin priorities"
run_sudo tee /etc/apt/preferences.d/isar >/dev/null <<'EOF'
Package: *
Pin: origin eci.intel.com
Pin-Priority: 1000

Package: libze-intel-gpu1,libze1,intel-opencl-icd,libze-dev,intel-ocloc
Pin: origin repositories.intel.com/gpu/ubuntu
Pin-Priority: 1000
EOF

log "Enabling Ubuntu universe repository"
run_sudo add-apt-repository -y universe

log "Installing ROS 2 key"
run_sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

if [[ "$FIX_RAW_GITHUB_HOST" == true ]]; then
  log "Applying raw.githubusercontent.com hosts workaround"
  if ! grep -qE '^[[:space:]]*185\.199\.108\.133[[:space:]]+raw\.githubusercontent\.com([[:space:]]|$)' /etc/hosts; then
    echo '185.199.108.133 raw.githubusercontent.com' | run_sudo tee -a /etc/hosts >/dev/null
  fi
fi

log "Configuring ROS 2 APT repository list"
ROS_CODENAME="$(. /etc/os-release && echo "$UBUNTU_CODENAME")"
ARCH="$(dpkg --print-architecture)"
run_sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null <<EOF
deb [arch=${ARCH} signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu ${ROS_CODENAME} main
EOF

log "Refreshing apt package indexes"
run_sudo apt update

log "Locale after setup:"
locale || true

log "OS setup script completed"