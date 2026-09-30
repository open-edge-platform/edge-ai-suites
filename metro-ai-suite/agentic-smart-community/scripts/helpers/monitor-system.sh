#!/bin/bash
# Periodic system snapshot logger: CPU%, memory%, NPU%.
# Writes one CSV row every INTERVAL seconds (default 1800s = 30min) into
# results/system_monitor_<YYYYMMDD-HHMMSS>.csv (file timestamp = first sample).
#
# Usage:
#   bash scripts/monitor-system.sh                # 30 min interval, runs forever
#   bash scripts/monitor-system.sh 600            # 10 min interval
#   bash scripts/monitor-system.sh 1800 86400     # 30 min interval, stop after 1 day
#
# Sampling:
#   CPU%        : 1s delta over /proc/stat aggregate cpu line (idle+iowait excluded)
#   MEM%/used/total (GiB)  : from /proc/meminfo; used  = MemTotal  - MemAvailable
#                            NOTE: this is the strict "unavailable" figure, NOT the
#                            "used" you see in htop. htop = Total - Free - buff/cache + Shmem,
#                            which assumes ALL buff/cache is reclaimable. In reality the
#                            kernel can hold significant cache that is NOT reclaimable
#                            (dirty pages, active list, GPU/IOMMU-pinned). MemAvailable
#                            accounts for this — it's what an allocator can actually grab
#                            without swapping. Expect this script's mem% to read several
#                            GiB higher than htop on busy systems; that gap is a useful
#                            signal of fragmentation / pinned cache pressure.
#   SWAP%/used (GiB)       : from /proc/meminfo; used  = SwapTotal - SwapFree
#                            (swap total is constant; not logged)
#   NPU%        : Intel intel_vpu npu_busy_time_us delta over a 1s window
#
# On exit (Ctrl+C, SIGTERM, or DURATION reached) the script prints
# avg/peak CPU% and NPU% across all collected samples.

set -u

INTERVAL="${1:-1800}"
DURATION="${2:-0}"   # 0 = forever

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$ROOT_DIR/results"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/system_monitor_$(date +%Y%m%d-%H%M%S).csv"

NPU_BUSY_PATH=""
for p in /sys/bus/pci/devices/*/npu_busy_time_us; do
  [[ -r "$p" ]] && NPU_BUSY_PATH="$p" && break
done

SAMPLE_WINDOW=1   # seconds used to compute the CPU/NPU rate at each tick

read_cpu_aggregate() {
  # echoes "total idle" for the aggregate "cpu" line in /proc/stat
  local line user nice sys idle iowait irq soft steal
  read -r line < /proc/stat
  read -r _ user nice sys idle iowait irq soft steal _ <<< "$line"
  iowait=${iowait:-0}; irq=${irq:-0}; soft=${soft:-0}; steal=${steal:-0}
  echo "$((user + nice + sys + idle + iowait + irq + soft + steal)) $((idle + iowait))"
}

sample_cpu_pct() {
  local t1 i1 t2 i2 dt di
  read t1 i1 <<< "$(read_cpu_aggregate)"
  sleep "$SAMPLE_WINDOW"
  read t2 i2 <<< "$(read_cpu_aggregate)"
  dt=$(( t2 - t1 ))
  di=$(( i2 - i1 ))
  if (( dt > 0 )); then
    local pct=$(( (dt - di) * 100 / dt ))
    (( pct < 0 )) && pct=0
    (( pct > 100 )) && pct=100
    echo "$pct"
  else
    echo "0"
  fi
}

sample_mem_swap() {
  # Single /proc/meminfo read -> "mem_pct mem_used_gib mem_total_gib swap_pct swap_used_gib swap_total_gib"
  awk '
    /^MemTotal:/      { mt = $2 }
    /^MemAvailable:/  { ma = $2 }
    /^SwapTotal:/     { st = $2 }
    /^SwapFree:/      { sf = $2 }
    END {
      mu = mt - ma
      mp = (mt > 0) ? int(mu * 100 / mt) : 0
      su = st - sf
      sp = (st > 0) ? int(su * 100 / st) : 0
      printf "%d %.2f %.2f %d %.2f %.2f\n",
             mp, mu / 1048576, mt / 1048576,
             sp, su / 1048576, st / 1048576
    }' /proc/meminfo
}

sample_npu_pct() {
  [[ -z "$NPU_BUSY_PATH" ]] && { echo ""; return; }
  local b1 b2 w1 w2 db dw
  b1=$(cat "$NPU_BUSY_PATH" 2>/dev/null || echo "")
  w1=$(date +%s%N)
  [[ -z "$b1" || ! "$b1" =~ ^[0-9]+$ ]] && { echo ""; return; }
  sleep "$SAMPLE_WINDOW"
  b2=$(cat "$NPU_BUSY_PATH" 2>/dev/null || echo "")
  w2=$(date +%s%N)
  [[ -z "$b2" || ! "$b2" =~ ^[0-9]+$ ]] && { echo ""; return; }
  db=$(( b2 - b1 ))
  dw=$(( w2 - w1 ))
  (( dw <= 0 )) && { echo ""; return; }
  # pct = db_us / dw_us * 100 = db * 100 * 1000 / dw_ns
  local pct=$(( db * 100000 / dw ))
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  echo "$pct"
}

echo "timestamp,cpu_pct,mem_pct,mem_used_gib,mem_total_gib,swap_pct,swap_used_gib,npu_pct" > "$OUT_FILE"

START_TS=$(date +%s)
echo "[monitor-system] interval=${INTERVAL}s duration=${DURATION}s output=$OUT_FILE"
[[ -z "$NPU_BUSY_PATH" ]] && echo "[monitor-system] NPU not detected (intel_vpu sysfs missing); npu_pct will be empty"

# Running aggregates for the on-exit summary.
SAMPLE_COUNT=0
CPU_SUM=0; CPU_PEAK=0
NPU_SUM=0; NPU_PEAK=0; NPU_VALID_COUNT=0

on_exit() {
  local elapsed=$(( $(date +%s) - START_TS ))
  echo ""
  echo "=========================================="
  echo "  monitor-system summary (${elapsed}s, ${SAMPLE_COUNT} samples)"
  echo "=========================================="
  if (( SAMPLE_COUNT > 0 )); then
    local cpu_avg=$(( CPU_SUM / SAMPLE_COUNT ))
    printf "  CPU  avg: %3d%%   peak: %3d%%\n" "$cpu_avg" "$CPU_PEAK"
  else
    printf "  CPU  no samples\n"
  fi
  if (( NPU_VALID_COUNT > 0 )); then
    local npu_avg=$(( NPU_SUM / NPU_VALID_COUNT ))
    printf "  NPU  avg: %3d%%   peak: %3d%%\n" "$npu_avg" "$NPU_PEAK"
  elif [[ -n "$NPU_BUSY_PATH" ]]; then
    printf "  NPU  no valid samples\n"
  else
    printf "  NPU  not detected (intel_vpu sysfs missing)\n"
  fi
  echo "  log: $OUT_FILE"
  echo "=========================================="
  exit 0
}
trap on_exit INT TERM

while true; do
  # CPU and NPU each consume SAMPLE_WINDOW seconds; run them sequentially so
  # both windows are well-defined. Memory is an instantaneous read.
  cpu_pct=$(sample_cpu_pct)
  npu_pct=$(sample_npu_pct)
  read mem_pct mem_used_gib mem_total_gib swap_pct swap_used_gib swap_total_gib <<< "$(sample_mem_swap)"
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo "${ts},${cpu_pct},${mem_pct},${mem_used_gib},${mem_total_gib},${swap_pct},${swap_used_gib},${npu_pct}" >> "$OUT_FILE"
  echo "[monitor-system] ${ts}  cpu=${cpu_pct}%  mem=${mem_pct}% (${mem_used_gib}/${mem_total_gib} GiB)  swap=${swap_pct}% (${swap_used_gib} GiB)  npu=${npu_pct:-N/A}%"

  # Update running aggregates.
  CPU_SUM=$(( CPU_SUM + cpu_pct ))
  (( cpu_pct > CPU_PEAK )) && CPU_PEAK=$cpu_pct
  if [[ -n "$npu_pct" ]]; then
    NPU_SUM=$(( NPU_SUM + npu_pct ))
    NPU_VALID_COUNT=$(( NPU_VALID_COUNT + 1 ))
    (( npu_pct > NPU_PEAK )) && NPU_PEAK=$npu_pct
  fi
  SAMPLE_COUNT=$(( SAMPLE_COUNT + 1 ))

  if (( DURATION > 0 )) && (( $(date +%s) - START_TS >= DURATION )); then
    echo "[monitor-system] duration reached, exit"
    on_exit
  fi

  # Subtract the sampling windows (cpu + npu, ~2s) so the cadence stays close
  # to INTERVAL. Round any small drift away if INTERVAL is small.
  sleep_for=$(( INTERVAL - 2 * SAMPLE_WINDOW ))
  (( sleep_for < 1 )) && sleep_for=1
  sleep "$sleep_for"
done
