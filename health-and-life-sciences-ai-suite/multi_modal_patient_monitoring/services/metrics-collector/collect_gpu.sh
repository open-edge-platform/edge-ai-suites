#!/bin/bash
#
# collect_gpu.sh -- bounded Intel GPU stats collection via qmassa.
#
# This file deliberately OVERRIDES /scripts/collect_gpu.sh from the
# intel/retail-benchmark base image (supervisord's [program:gpu_metrics]
# invokes that path, so replacing the file is enough -- no supervisord edit).
#
# WHY THIS OVERRIDE EXISTS
# ------------------------
# `qmassa -t <file>` accumulates every sample it has ever taken in memory and
# rewrites the *entire* JSON document on each update (default every 1500 ms).
# Nothing in qmassa rotates, truncates or caps that file: there is no ring
# buffer option (`-n/--nr-iterations` only bounds the run before it exits).
#
# Left running, that is unbounded growth in three dimensions at once:
#
#   * disk   -- measured at ~596 MB/hour on this platform (2.4 GB after 4 h,
#               and it never stops)
#   * qmassa RSS -- it holds all states in memory to be able to rewrite them
#   * reader cost -- metrics.py must json.load() the whole document to obtain
#               the last 60 points the dashboard actually plots
#
# The third one is what took the service down: a 2.4 GB json.load() needs
# ~15-20 GB of RAM and tens of seconds of CPU, on every single /metrics poll.
# It pinned the container at 112% CPU / 4.2 GiB RSS, made every endpoint take
# 20-40 s, and starved the healthcheck into a permanent failing state.
#
# The fix is to bound qmassa's run: collect for a fixed window, let qmassa
# exit, delete the file, and start a fresh one. Both the file and qmassa's
# memory are then bounded by the window rather than by uptime.
#
# Losing history at each cycle is harmless because build_gpu_series() in
# metrics.py keeps its own rolling series across restarts -- the chart is
# continuous even though the underlying file is not.

set -uo pipefail

RESULTS_DIR="${METRICS_DIR:-/tmp/results}"

# Sampling interval passed to qmassa, in milliseconds.
QMASSA_MS_INTERVAL="${QMASSA_MS_INTERVAL:-1500}"

# How many samples to collect before recycling the file. 120 x 1500 ms = 3
# minutes, which caps the JSON at roughly 30 MB on this platform while still
# holding far more than the 60 points the dashboard renders.
QMASSA_CYCLE_ITERATIONS="${QMASSA_CYCLE_ITERATIONS:-120}"

QMASSA_BIN="${QMASSA_BIN:-$HOME/.cargo/bin/qmassa}"
if [[ ! -x "${QMASSA_BIN}" ]]; then
    QMASSA_BIN="/root/.cargo/bin/qmassa"
fi

mkdir -p "${RESULTS_DIR}"

# ---------------------------------------------------------------------------
# Discover the first supported GPU (same logic as the base image script).
# ---------------------------------------------------------------------------
mapfile -t pci_devices < <(
  for card in /dev/dri/card*; do
    [[ -e "$card" ]] || continue
    pci_id=$(udevadm info --query=all --name="$card" 2>/dev/null \
        | grep -w DEVPATH | cut -d= -f2 \
        | grep -oE '[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]' | tail -1)
    [[ -n "$pci_id" ]] || continue
    pci_info=$(lspci -s "$pci_id" -nn | head -n1)
    if echo "$pci_info" | grep -iq "VGA compatible controller"; then
      vendor_device=$(echo "$pci_info" | grep -oP '\[\K[0-9a-f]{4}:[0-9a-f]{4}(?=\])')
      device=${vendor_device##*:}
      driver=$(lspci -k -s "$pci_id" | grep "Kernel driver in use:" | awk '{print $5}')
      card_num=${card##*card}
      echo "pci:$pci_id,device=$device,card=$card_num,driver=$driver"
    fi
  done
)

if [ ${#pci_devices[@]} -eq 0 ]; then
    echo "[collect_gpu] No supported PCI GPU device found; GPU metrics disabled."
    # Sleep rather than exit: exiting makes supervisord restart us in a tight
    # loop, which is far noisier than simply having no GPU series.
    while true; do sleep 3600; done
fi

device_line="${pci_devices[0]}"
driver=$(echo "$device_line" | grep -oP 'driver=\K\S+')
if [[ "$driver" != "i915" && "$driver" != "xe" && "$driver" != "amdgpu" ]]; then
    echo "[collect_gpu] Driver '$driver' unsupported (need i915/xe/amdgpu); GPU metrics disabled."
    while true; do sleep 3600; done
fi

pci_info="${device_line#pci:}"
pci_info="${pci_info%%,*}"
device_id=$(echo "$device_line" | grep -oP 'device=\K[^,]+')
card_num=$(echo "$device_line" | grep -oP '(?<=card=)[^,]+')

output_file="${RESULTS_DIR}/qmassa${card_num}-${device_id}-${driver}-tool-generated.json"

echo "[collect_gpu] device=${pci_info} driver=${driver} -> ${output_file}"
echo "[collect_gpu] bounded cycle: ${QMASSA_CYCLE_ITERATIONS} samples @ ${QMASSA_MS_INTERVAL}ms"

# ---------------------------------------------------------------------------
# Bounded collection loop.
# ---------------------------------------------------------------------------
while true; do
    # Start each cycle from an empty file so neither the JSON nor qmassa's
    # resident memory can grow with uptime.
    rm -f "${output_file}"
    touch "${output_file}"
    chown 1000:1000 "${output_file}" 2>/dev/null || true

    "${QMASSA_BIN}" \
        -d "${pci_info}" \
        -g -x \
        -m "${QMASSA_MS_INTERVAL}" \
        -n "${QMASSA_CYCLE_ITERATIONS}" \
        -t "${output_file}" \
        2>> "${RESULTS_DIR}/qmassa_error.log"

    # If qmassa dies immediately (permissions, driver hiccup) this loop would
    # otherwise spin. A short floor keeps a failure at ~1 restart/sec worst case.
    sleep 1
done
