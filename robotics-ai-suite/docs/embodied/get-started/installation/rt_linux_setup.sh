#!/usr/bin/env bash
#
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS_SETUP_SCRIPT="${SCRIPT_DIR}/../prerequisites/os_setup_install.sh"

KERNEL_FLAVOR="rt"
RUN_OS_SETUP=true
OS_SET_DATE=""
OS_DISABLE_AUTO_UPGRADES=false
OS_FIX_RAW_GITHUB_HOST=false
APPLY_RT_GRUB_TUNING=false
INSTALL_RT_TESTS=false
DISABLE_TIMER_MIGRATION=false
DISABLE_SWAP=false
CSTATE_CPU_RANGE=""

print_usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options]

Automates the setup flow in docs/embodied/get-started/installation/rt_linux.rst
and linked prerequisites/docs references, including invoking os_setup_install.sh.

Options:
  --skip-os-setup                  Skip calling os_setup_install.sh
  --os-set-date "YYYY-MM-DD HH:MM" Pass date setting to os_setup_install.sh
  --os-disable-auto-upgrades       Pass auto-upgrade disable to os_setup_install.sh
  --os-fix-raw-github-host         Pass DNS workaround to os_setup_install.sh

  --kernel rt|generic              Kernel flavor to install (default: rt)
  --apply-rt-grub-tuning           Apply grub sed tuning from rt_linux.rst and run update-grub

  --disable-timer-migration        Set /proc/sys/kernel/timer_migration to 0
  --disable-swap                   Run swapoff -a
  --disable-cstate-cpus START-END  Disable cpuidle states (state1..max) for CPU range

  --install-rt-tests               Install deps and build rt-tests-2.6 (cyclictest)
  -h, --help                       Show this help

Notes:
  - Requires Ubuntu with sudo/root privileges.
  - Reboot and selecting the target grub entry are manual steps.
  - CAT/DVFS MSR examples in the guide are platform-specific and not auto-applied.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-os-setup)
      RUN_OS_SETUP=false
      ;;
    --os-set-date)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --os-set-date" >&2; exit 1; }
      OS_SET_DATE="$1"
      ;;
    --os-disable-auto-upgrades)
      OS_DISABLE_AUTO_UPGRADES=true
      ;;
    --os-fix-raw-github-host)
      OS_FIX_RAW_GITHUB_HOST=true
      ;;
    --kernel)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --kernel" >&2; exit 1; }
      KERNEL_FLAVOR="$1"
      ;;
    --apply-rt-grub-tuning)
      APPLY_RT_GRUB_TUNING=true
      ;;
    --install-rt-tests)
      INSTALL_RT_TESTS=true
      ;;
    --disable-timer-migration)
      DISABLE_TIMER_MIGRATION=true
      ;;
    --disable-swap)
      DISABLE_SWAP=true
      ;;
    --disable-cstate-cpus)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --disable-cstate-cpus" >&2; exit 1; }
      CSTATE_CPU_RANGE="$1"
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

case "$KERNEL_FLAVOR" in
  rt|generic)
    ;;
  *)
    echo "Invalid --kernel value: $KERNEL_FLAVOR (must be rt or generic)" >&2
    exit 1
    ;;
esac

log() {
  echo "[rt-linux-setup] $*"
}

log_skipped_section() {
  log "Skipped section: $1"
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

log "Selected flow: kernel=${KERNEL_FLAVOR}, run-os-setup=${RUN_OS_SETUP}, apply-rt-grub-tuning=${APPLY_RT_GRUB_TUNING}, disable-timer-migration=${DISABLE_TIMER_MIGRATION}, disable-swap=${DISABLE_SWAP}, disable-cstate-cpus=${CSTATE_CPU_RANGE:-none}, install-rt-tests=${INSTALL_RT_TESTS}"

# Log sections from rt_linux.rst that are intentionally skipped in this run.
[[ "$RUN_OS_SETUP" == false ]] && log_skipped_section "Prerequisites OS setup script invocation"
[[ "$KERNEL_FLAVOR" != "rt" ]] && log_skipped_section "Install the real-time Linux kernel (linux-intel-rt-experimental)"
[[ "$KERNEL_FLAVOR" != "generic" ]] && log_skipped_section "Install generic kernel alternative (linux-intel-experimental note)"
[[ "$APPLY_RT_GRUB_TUNING" == false ]] && log_skipped_section "GRUB cmdline tuning edits in /etc/grub.d/10_eci_experimental"
[[ "$DISABLE_TIMER_MIGRATION" == false ]] && log_skipped_section "Timer Migration Disable runtime tuning"
[[ "$DISABLE_SWAP" == false ]] && log_skipped_section "Disable Swap runtime tuning"
[[ -z "$CSTATE_CPU_RANGE" ]] && log_skipped_section "Per-core C-State Disable runtime tuning"
[[ "$INSTALL_RT_TESTS" == false ]] && log_skipped_section "Verify Benchmark Performance helper (rt-tests download/build)"
log_skipped_section "Select [Experimental] ECI Ubuntu boot entry after reboot (manual)"
log_skipped_section "Use Cache Allocation Technology example (manual/platform specific)"
log_skipped_section "Use Dynamic Voltage and Frequency example (manual/platform specific)"

if [[ "$RUN_OS_SETUP" == true ]]; then
  if [[ ! -x "$OS_SETUP_SCRIPT" ]]; then
    echo "Cannot execute OS setup script: $OS_SETUP_SCRIPT" >&2
    exit 1
  fi

  log "Running prerequisite OS setup script"
  os_args=()
  [[ -n "$OS_SET_DATE" ]] && os_args+=(--set-date "$OS_SET_DATE")
  [[ "$OS_DISABLE_AUTO_UPGRADES" == true ]] && os_args+=(--disable-auto-upgrades)
  [[ "$OS_FIX_RAW_GITHUB_HOST" == true ]] && os_args+=(--fix-raw-github-host)
  "$OS_SETUP_SCRIPT" "${os_args[@]}"
else
  log "Skipping OS setup script (--skip-os-setup)"
fi

require_cmd apt
require_cmd dpkg

log "Installing GRUB customizations and linux-firmware"
run_sudo apt update
run_sudo apt install -y customizations-grub linux-firmware

if [[ -d /lib/firmware/i915/experimental ]]; then
  if ls /lib/firmware/i915/experimental/mtl_{guc_70.bin,dmc.bin,gsc_1.bin} >/dev/null 2>&1; then
    log "Detected expected i915 experimental firmware files"
  else
    log "Warning: i915 experimental firmware files not fully found in /lib/firmware/i915/experimental/"
    log "If needed, install the firmware version documented in rt_linux.rst"
  fi
else
  log "Warning: /lib/firmware/i915/experimental/ not found"
fi

if [[ "$KERNEL_FLAVOR" == "rt" ]]; then
  log "Installing real-time kernel package: linux-intel-rt-experimental"
  run_sudo apt install -y linux-intel-rt-experimental
else
  log "Installing generic kernel package: linux-intel-experimental"
  run_sudo apt install -y linux-intel-experimental
fi

if [[ "$APPLY_RT_GRUB_TUNING" == true ]]; then
  GRUB_FILE="/etc/grub.d/10_eci_experimental"
  if [[ -f "$GRUB_FILE" ]]; then
    log "Applying rt_linux.rst GRUB tuning to ${GRUB_FILE}"
    run_sudo sed -i 's/intel_pstate=disable intel.max_cstate=0 intel_idle.max_cstate=0 processor.max_cstate=0 processor_idle.max_cstate=0/intel_pstate=enable/g' "$GRUB_FILE"
    run_sudo sed -i 's/irqaffinity=0 /irqaffinity=0-9 /g' "$GRUB_FILE"
    run_sudo sed -i 's/isolcpus=${isolcpus} rcu_nocbs=${isolcpus} nohz_full=${isolcpus}/isolcpus=10-13 rcu_nocbs=10-13 nohz_full=10-13/g' "$GRUB_FILE"
    run_sudo update-grub
  else
    log "Warning: ${GRUB_FILE} not found; skipping GRUB tuning"
  fi
fi

if [[ "$DISABLE_TIMER_MIGRATION" == true ]]; then
  log "Disabling timer migration"
  run_sudo sh -c 'echo 0 > /proc/sys/kernel/timer_migration'
fi

if [[ "$DISABLE_SWAP" == true ]]; then
  log "Disabling swap"
  run_sudo swapoff -a
fi

if [[ -n "$CSTATE_CPU_RANGE" ]]; then
  if [[ "$CSTATE_CPU_RANGE" =~ ^([0-9]+)-([0-9]+)$ ]]; then
    cpu_start="${BASH_REMATCH[1]}"
    cpu_end="${BASH_REMATCH[2]}"
  else
    echo "Invalid --disable-cstate-cpus value: $CSTATE_CPU_RANGE (expected START-END)" >&2
    exit 1
  fi

  log "Disabling per-core C-states for CPUs ${cpu_start}-${cpu_end}"
  for ((cpu=cpu_start; cpu<=cpu_end; cpu++)); do
    cpuidle_dir="/sys/devices/system/cpu/cpu${cpu}/cpuidle"
    if [[ ! -d "$cpuidle_dir" ]]; then
      log "Warning: ${cpuidle_dir} not found; skipping CPU ${cpu}"
      continue
    fi

    max_state_index="$(ls "$cpuidle_dir" | grep -o 'state[0-9]*' | sed 's/state//' | sort -n | tail -1 || true)"
    if [[ -z "$max_state_index" ]]; then
      log "Warning: no cpuidle states found for CPU ${cpu}"
      continue
    fi

    for ((state=1; state<=max_state_index; state++)); do
      disable_file="${cpuidle_dir}/state${state}/disable"
      if [[ -f "$disable_file" ]]; then
        run_sudo sh -c "echo 1 > '$disable_file'"
      fi
    done
  done
fi

if [[ "$INSTALL_RT_TESTS" == true ]]; then
  log "Installing cyclictest build dependency"
  run_sudo apt install -y libnuma-dev

  work_dir="${PWD}/rt-tests-2.6"
  tarball="${PWD}/rt-tests-2.6.tar.gz"
  if [[ ! -d "$work_dir" ]]; then
    log "Downloading and building rt-tests-2.6"
    require_cmd wget
    require_cmd tar
    require_cmd make
    wget -O "$tarball" https://web.git.kernel.org/pub/scm/utils/rt-tests/rt-tests.git/snapshot/rt-tests-2.6.tar.gz
    tar zxvf "$tarball"
    (cd "$work_dir" && make)
  else
    log "Found existing ${work_dir}; skipping download/build"
  fi
fi

log "Setup complete. Reboot and select [Experimental] ECI Ubuntu entry in GRUB."
log "After reboot, verify with: uname -r && cat /proc/cmdline"
