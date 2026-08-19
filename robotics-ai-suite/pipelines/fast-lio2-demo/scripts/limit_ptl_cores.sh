#!/usr/bin/env bash
# Lock CPU governor + min/max frequency per core cluster on Intel PTL
# (Core Ultra X7 358H) for apples-to-apples benchmarking, then reinforce the
# limit with a direct HWP MSR write. Requires root (sysfs + MSR writes).
#
# Best-effort throughout: a platform that doesn't expose these cpufreq
# knobs at all, or is missing msr-tools, is an accepted non-fatal outcome -
# each failure is warned about, not fatal, so this never blocks
# reproduce_all.sh or any other caller.
#
# Usage: sudo ./limit_ptl_cores.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

if [[ "${EUID}" -ne 0 ]]; then
  echo "limit_ptl_cores.sh writes to /sys/devices/system/cpu/*/cpufreq and" >&2
  echo "MSR 0x774; both require root. Re-run as:" >&2
  echo "  sudo ${SCRIPT_DIR}/limit_ptl_cores.sh" >&2
  exit 1
fi

P_CORES="${FREQ_P_CORES}"
E_CORES="${FREQ_E_CORES}"
LPE_CORES="${FREQ_LPE_CORES}"
P_MAX="${FREQ_P_MAX}"; P_MIN="${FREQ_P_MIN}"
E_MAX="${FREQ_E_MAX}"; E_MIN="${FREQ_E_MIN}"
LPE_MAX="${FREQ_LPE_MAX}"; LPE_MIN="${FREQ_LPE_MIN}"
GOV_P="${CPU_MODE_P}"
GOV_E="${CPU_MODE_E}"

# Apply governor + min/max to one core group. Every sysfs write is guarded
# by `if ! ...; then WARN; fi` rather than a bare `echo > file`, on purpose:
# an individual write can be legitimately rejected per-core (read-only
# policy, unsupported governor, offline cpu) and that's expected/recoverable
# - it must not trip `set -e` and abort the whole run.
set_limit() {
  local cores="$1" minfreq="$2" maxfreq="$3" governor="$4" name="$5"
  local c p avail
  for c in $cores; do
    p="/sys/devices/system/cpu/cpufreq/policy${c}"
    if [[ ! -d "$p" ]]; then
      echo "WARN: ${p} not found (cpu${c} offline or no cpufreq policy), skipped" >&2
      continue
    fi
    if [[ -f "${p}/scaling_governor" ]]; then
      if ! echo "$governor" > "${p}/scaling_governor" 2>/dev/null; then
        avail="$(cat "${p}/scaling_available_governors" 2>/dev/null || echo unknown)"
        echo "WARN: governor '${governor}' rejected for cpu${c} (available: ${avail}), skipped" >&2
      fi
    fi
    # Set max before min to avoid a transient min>max rejection by the kernel.
    if [[ -f "${p}/scaling_max_freq" ]]; then
      if ! echo "$maxfreq" > "${p}/scaling_max_freq" 2>/dev/null; then
        echo "WARN: failed to set max_freq=${maxfreq} for cpu${c}, skipped" >&2
      fi
    fi
    if [[ "$minfreq" -gt 0 && -f "${p}/scaling_min_freq" ]]; then
      if ! echo "$minfreq" > "${p}/scaling_min_freq" 2>/dev/null; then
        echo "WARN: failed to set min_freq=${minfreq} for cpu${c}, skipped" >&2
      fi
    fi
    echo "${name} cpu${c} -> governor=${governor} min=${minfreq} max=${maxfreq} kHz"
  done
}

echo "==> Locking governor + min/max frequency per core cluster"
set_limit "${P_CORES}" "${P_MIN}" "${P_MAX}" "${GOV_P}" "P-core"
set_limit "${E_CORES}" "${E_MIN}" "${E_MAX}" "${GOV_E}" "E-core"
set_limit "${LPE_CORES}" "${LPE_MIN}" "${LPE_MAX}" "${GOV_E}" "LP-E-core"

# HWP hardware-level lock via MSR 0x774 (IA32_HWP_REQUEST): a stronger
# override than the sysfs cpufreq knobs above, since HWP firmware can drift
# above the sysfs max under bursty load unless HWP itself is pinned.
# Best-effort: skipped with a warning if msr-tools/the msr module aren't
# available. The script is already root (checked above), so these calls
# are not re-wrapped in sudo.
#
# NOTE: the hex constants below encode P=4700MHz/E=3500MHz/LPE=3300MHz with
# EPP pinned to "Performance", matching the FREQ_*_MAX/MIN defaults in
# env.sh. If you change those variables, update these constants to match -
# they are not derived from FREQ_* automatically.
echo
if command -v wrmsr &>/dev/null && modprobe msr 2>/dev/null; then
  echo "==> Writing HWP MSR 0x774 (IA32_HWP_REQUEST) per core"
  for c in ${P_CORES}; do
    wrmsr 0x774 -p "$c" 0xf000000000353535 2>/dev/null \
      || echo "WARN: wrmsr failed on cpu${c}" >&2
  done
  for c in ${E_CORES}; do
    wrmsr 0x774 -p "$c" 0xf000000000252525 2>/dev/null \
      || echo "WARN: wrmsr failed on cpu${c}" >&2
  done
  for c in ${LPE_CORES}; do
    wrmsr 0x774 -p "$c" 0xf000000000212121 2>/dev/null \
      || echo "WARN: wrmsr failed on cpu${c}" >&2
  done
  echo "HWP MSR 0x774 written: P=0x35(~4.7GHz) E=0x25(~3.5GHz) LPE=0x21(~3.3GHz) EPP=Performance"
else
  echo "WARN: wrmsr not available or msr module failed to load - HWP hardware lock skipped" >&2
  echo "      (sysfs governor/min/max above is still applied)" >&2
fi

echo
echo "Current limits:"
for c in $(seq 0 15); do
  p="/sys/devices/system/cpu/cpufreq/policy${c}"
  [[ -f "${p}/scaling_max_freq" ]] || continue
  cluster="$(cat "/sys/devices/system/cpu/cpu${c}/topology/cluster_id" 2>/dev/null || echo '?')"
  governor="$(cat "${p}/scaling_governor" 2>/dev/null || echo '?')"
  minf="$(cat "${p}/scaling_min_freq" 2>/dev/null || echo '?')"
  maxf="$(cat "${p}/scaling_max_freq" 2>/dev/null || echo '?')"
  curf="$(cat "${p}/scaling_cur_freq" 2>/dev/null || echo '?')"
  printf "cpu%-2s cluster=%-3s governor=%-12s min=%-9s max=%-9s cur=%s\n" \
    "$c" "$cluster" "$governor" "$minf" "$maxf" "$curf"
done
