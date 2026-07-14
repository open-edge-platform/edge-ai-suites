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

Automates the software steps from docs/embodied/get-started/prerequisites/os_setup.md
and its included pages (locale + APT repositories).

Options:
  --set-date "YYYY-MM-DD HH:MM"   Set system date/time via: date -s
  --disable-auto-upgrades          Disable Ubuntu auto-upgrade settings
  --fix-raw-github-host            Add 185.199.108.133 raw.githubusercontent.com to /etc/hosts
  --dry-run                        Print commands without making system changes
  -h, --help                       Show this help message

Notes:
  - Ubuntu installation and BIOS setup are manual and cannot be automated by script.
  - Script supports Ubuntu 22.04 Desktop and Ubuntu 24.04 Desktop.
  - Script requires sudo/root.
EOF
}

SET_DATE=""
DISABLE_AUTO_UPGRADES=false
FIX_RAW_GITHUB_HOST=false
DRY_RUN=false

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
    --dry-run)
      DRY_RUN=true
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
  if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] $(printf '%q ' "$@")"
    return 0
  fi

  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo -E "$@"
  fi
}

run_shell() {
  local cmd="$1"

  if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] $cmd"
    return 0
  fi

  if [[ "${EUID}" -eq 0 ]]; then
    bash -c "$cmd"
  else
    sudo -E bash -c "$cmd"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

UBUNTU_VERSION=""
UBUNTU_CODENAME=""
ROS_DISTRO_HINT=""
CURL_PROXY_ARGS=()

init_curl_proxy_from_env() {
  local proxy_value="${https_proxy:-${HTTPS_PROXY:-${http_proxy:-${HTTP_PROXY:-}}}}"
  local no_proxy_value="${no_proxy:-${NO_PROXY:-}}"

  [[ -n "$proxy_value" ]] && CURL_PROXY_ARGS+=(--proxy "$proxy_value")
  [[ -n "$no_proxy_value" ]] && CURL_PROXY_ARGS+=(--noproxy "$no_proxy_value")

  if [[ ${#CURL_PROXY_ARGS[@]} -gt 0 ]]; then
    log "Detected proxy environment for curl/wget"
  fi
}

detect_supported_ubuntu() {
  if [[ ! -r /etc/os-release ]]; then
    echo "Cannot read /etc/os-release" >&2
    exit 1
  fi

  # shellcheck disable=SC1091
  source /etc/os-release

  if [[ "${ID:-}" != "ubuntu" ]]; then
    echo "Unsupported OS: ${PRETTY_NAME:-unknown}. Only Ubuntu is supported." >&2
    exit 1
  fi

  UBUNTU_VERSION="${VERSION_ID:-}"
  UBUNTU_CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"

  case "$UBUNTU_VERSION" in
    22.04)
      ROS_DISTRO_HINT="humble"
      log "Detected Ubuntu 22.04 (${UBUNTU_CODENAME}) branch"
      ;;
    24.04)
      ROS_DISTRO_HINT="jazzy"
      log "Detected Ubuntu 24.04 (${UBUNTU_CODENAME}) branch"
      ;;
    *)
      echo "Unsupported Ubuntu version: ${UBUNTU_VERSION}. Supported versions: 22.04, 24.04." >&2
      exit 1
      ;;
  esac
}

log "Manual prerequisites from guide:"
log "1) Install Ubuntu 22.04 or Ubuntu 24.04 Desktop (64-bit)"
log "2) Configure BIOS according to Step 4 in the OS Setup guide"

detect_supported_ubuntu
if [[ "$DRY_RUN" == true ]]; then
  log "Dry-run mode enabled: no changes will be made"
fi
init_curl_proxy_from_env

require_cmd apt
require_cmd dpkg
require_cmd tee
require_cmd mktemp

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
run_sudo wget -O /usr/share/keyrings/eci-archive-keyring.gpg https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg

log "Configuring Intel ECI APT repository list"
run_sudo tee /etc/apt/sources.list.d/eci.list >/dev/null <<EOF
deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main
deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main
EOF

if [[ "$DISABLE_AUTO_UPGRADES" == true ]]; then
  log "Disabling auto-upgrades in apt periodic configs"
  run_sudo sed -i 's/APT::Periodic::Update-Package-Lists "1"/APT::Periodic::Update-Package-Lists "0"/g' /etc/apt/apt.conf.d/20auto-upgrades || true
  run_sudo sed -i 's/APT::Periodic::Unattended-Upgrade "1"/APT::Unattended-Upgrade "0"/g' /etc/apt/apt.conf.d/20auto-upgrades || true
  run_sudo sed -i 's/APT::Periodic::Update-Package-Lists "1"/APT::Periodic::Update-Package-Lists "0"/' /etc/apt/apt.conf.d/10periodic || true
  run_sudo sed -i 's/APT::Periodic::Download-Upgradeable-Packages "1"/APT::Periodic::Download-Upgradeable-Packages "0"/' /etc/apt/apt.conf.d/10periodic || true
  run_sudo sed -i 's/APT::Periodic::AutocleanInterval "1"/APT::Periodic::AutocleanInterval "0"/' /etc/apt/apt.conf.d/10periodic || true
  run_shell 'echo "Hidden=true" | tee -a /etc/xdg/autostart/update-notifier.desktop > /dev/null'
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

if [[ "$FIX_RAW_GITHUB_HOST" == true ]]; then
  log "Applying raw.githubusercontent.com hosts workaround"
  if ! grep -qE '^[[:space:]]*185\.199\.108\.133[[:space:]]+raw\.githubusercontent\.com([[:space:]]|$)' /etc/hosts; then
    run_shell "echo '185.199.108.133 raw.githubusercontent.com' | tee -a /etc/hosts > /dev/null"
  fi
fi

log "Configuring ROS 2 repository using ros2-apt-source package"
if [[ "$DRY_RUN" == true ]]; then
  ROS_APT_SOURCE_VERSION="<latest-release-tag>"
  log "[dry-run] curl ${CURL_PROXY_ARGS[*]} -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F \"tag_name\" | awk -F'\"' '{print \$4}'"
else
  ROS_APT_SOURCE_VERSION="$(curl "${CURL_PROXY_ARGS[@]}" -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}')"
  if [[ -z "$ROS_APT_SOURCE_VERSION" ]]; then
    echo "Failed to resolve ros2-apt-source latest release version" >&2
    exit 1
  fi
fi

ROS_APT_DEB="$(mktemp /tmp/ros2-apt-source.XXXXXX.deb)"
if [[ "$DRY_RUN" == true ]]; then
  log "[dry-run] curl ${CURL_PROXY_ARGS[*]} -L -o $ROS_APT_DEB https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.${UBUNTU_CODENAME}_all.deb"
else
  curl "${CURL_PROXY_ARGS[@]}" -L -o "$ROS_APT_DEB" "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.${UBUNTU_CODENAME}_all.deb"
fi
run_sudo dpkg -i "$ROS_APT_DEB"
run_sudo rm -f "$ROS_APT_DEB"
log "ROS 2 apt source package installed for ${UBUNTU_CODENAME} (recommended distro: ${ROS_DISTRO_HINT})"

log "Refreshing apt package indexes"
run_sudo apt update

log "Locale after setup:"
locale || true

log "OS setup script completed"