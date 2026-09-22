#!/usr/bin/env bash
# Optional production-equivalent DDS transport: switches from plain
# CycloneDDS (env.sh's default RMW) to CycloneDDS + iceoryx zero-copy
# shared memory for same-host pub/sub, matching what Bing's own
# run_live_benchmark.sh uses on PTL/Orin - see README.md "Optional:
# production-equivalent CycloneDDS + iceoryx shared-memory setup" and
# /work/misc/0052_point_lio_fast_lio2/reports/colleague_guide.md §4.4 (same
# setup, documented there for the point_lio_fast_lio2 benchmark harness).
#
# Entirely optional: run_ulhk.sh falls back to plain CycloneDDS (no SHM) if
# this was never run, or if USE_DDS_SHM=false in env.sh - customers/
# colleagues who don't want this extra moving part can just skip it.
#
# Usage: ./setup_dds_shm.sh [start|stop|status]   (default: start)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

ACTION="${1:-start}"

if [[ "${USE_DDS_SHM}" != "true" ]]; then
  echo "==> USE_DDS_SHM=false in env.sh, skipping CycloneDDS+iceoryx shared-memory setup"
  exit 0
fi

roudi_pid() {
  [[ -f "${ROUDI_PIDFILE}" ]] || return 1
  local pid
  pid="$(cat "${ROUDI_PIDFILE}")"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null && echo "${pid}"
}

# Kill every iox-roudi process on the box, whether or not it's the one
# ROUDI_PIDFILE currently tracks. An iox-roudi from an earlier run can
# outlive its own pidfile (e.g. this script's config changed and got
# re-run, or the pidfile was lost/overwritten by a since-interrupted run) -
# starting a second instance next to that orphan instead of replacing it
# leaves the orphan (with its STALE mempool config) as the one everything
# actually talks to. Always call this before starting a fresh one.
stop_all_roudi() {
  local pid any=false
  for pid in $(pgrep -x iox-roudi 2>/dev/null); do
    any=true
    kill "${pid}" 2>/dev/null || true
  done
  if "${any}"; then
    for _ in $(seq 1 20); do pgrep -x iox-roudi >/dev/null 2>&1 || break; sleep 0.1; done
    for pid in $(pgrep -x iox-roudi 2>/dev/null); do
      kill -9 "${pid}" 2>/dev/null || true
    done
  fi
  rm -f "${ROUDI_PIDFILE}"
}

do_status() {
  local pid
  if pid="$(roudi_pid)"; then
    echo "iox-roudi running (pid ${pid}, pidfile ${ROUDI_PIDFILE})"
  elif pgrep -x iox-roudi >/dev/null 2>&1; then
    echo "iox-roudi running (pid unknown - not started by this script's pidfile)"
  else
    echo "iox-roudi not running"
  fi
}

do_stop() {
  if pgrep -x iox-roudi >/dev/null 2>&1; then
    echo "==> Stopping iox-roudi"
    stop_all_roudi
  else
    echo "==> iox-roudi not running (nothing to stop)"
  fi
}

do_start() {
  echo "==> Installing CycloneDDS + iceoryx packages (sudo, safe to re-run)"
  sudo apt-get update -qq
  sudo apt-get install -y \
    "ros-${ROS_DISTRO}-cyclonedds" "ros-${ROS_DISTRO}-rmw-cyclonedds-cpp" \
    "ros-${ROS_DISTRO}-iceoryx-posh" "ros-${ROS_DISTRO}-iceoryx-hoofs" \
    "ros-${ROS_DISTRO}-iceoryx-binding-c"

  mkdir -p "${DDS_SHM_DIR}"

  # Own (non-loopback) NIC IP, for the unicast Peer entry below - same-host
  # discovery still needs an explicit Peer alongside AllowMulticast=true (see
  # the note on that setting further down).
  MY_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '/src/{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')"
  if [[ -z "${MY_IP}" ]]; then
    echo "Could not determine this host's own IP via 'ip route get 1.1.1.1'." >&2
    exit 1
  fi

  echo "==> Writing ${CYCLONEDDS_SHM_XML} (own IP: ${MY_IP})"
  cat > "${CYCLONEDDS_SHM_XML}" <<EOF
<CycloneDDS><Domain><General>
  <AllowMulticast>true</AllowMulticast>
</General><Discovery><Peers><Peer Address="${MY_IP}"/></Peers></Discovery>
<SharedMemory>
  <Enable>true</Enable>
  <LogLevel>warn</LogLevel>
</SharedMemory>
</Domain></CycloneDDS>
EOF
  # AllowMulticast must be "true" here, not "false": an earlier config used
  # false (multicast off, discovery via the unicast Peer only) as
  # defense-in-depth, but that combination reliably breaks same-host node
  # discovery on Orin (confirmed 2026-07-23 - see colleague_guide.md §4.4.2).
  # true + the Peer entry above discovers in ~1s on both PTL and Orin.

  echo "==> Writing ${ROUDI_CONFIG}"
  cat > "${ROUDI_CONFIG}" <<'EOF'
[general]
version = 1

[[segment]]

[[segment.mempool]]
size = 128
count = 10000

[[segment.mempool]]
size = 1024
count = 5000

[[segment.mempool]]
size = 16384
count = 1000

[[segment.mempool]]
size = 131072
count = 200

[[segment.mempool]]
size = 524288
count = 50

[[segment.mempool]]
size = 1048576
count = 30

[[segment.mempool]]
size = 4194304
count = 100
EOF
  # Mempool sizes are sized for full PointCloud2 scans (a few MB/frame) -
  # RouDi's own stock example config is too small for that and silently
  # drops SHM segments instead of erroring. The largest pool's count is set
  # to 100 (not the stock example's 20) matching the sibling point-lio-demo
  # pipeline's own fix: a full-length ulhk_4 run (~10Hz velodyne scans over
  # 5:21) there hit "MemoryManager: unable to acquire a chunk"/
  # MEPOO__MEMPOOL_GETCHUNK_POOL_IS_RUNNING_OUT_OF_CHUNKS with count=20 - the
  # real fix was ensuring ptl_wrap's SCHED_FIFO reprioritization actually
  # reaches the algorithm's real process (see run_ulhk.sh's ptl_wrap), but a
  # bigger pool gives headroom against any remaining transient backlog too.

  echo "==> Ensuring no stale/orphaned iox-roudi is left running before starting with this config"
  stop_all_roudi

  echo "==> Starting iox-roudi"
  set +u
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
  set -u
  # --monitoring-mode off is required, not optional: RouDi's default
  # liveness monitor evicts (silently drops SHM pub/sub for) any participant
  # that misses a ~1.5s heartbeat, which CPU isolation/governor/SCHED_FIFO
  # changes (see run_ulhk.sh's ptl_wrap) can easily trigger even though the
  # process is alive and working - this was the root cause of a real class
  # of "profiling.csv has 0 data rows" failures. Do not add
  # --killall-on-sigterm either - that flag doesn't exist in the iceoryx
  # build shipped for Jazzy or Humble and makes iox-roudi fail to start.
  nohup iox-roudi -c "${ROUDI_CONFIG}" --monitoring-mode off \
    > "${ROUDI_LOG}" 2>&1 &
  echo "$!" > "${ROUDI_PIDFILE}"

  sleep 2
  if pgrep -x iox-roudi >/dev/null 2>&1; then
    echo "==> iox-roudi is up (pid $(cat "${ROUDI_PIDFILE}"), log ${ROUDI_LOG})"
  else
    echo "iox-roudi failed to start - check ${ROUDI_LOG}:" >&2
    tail -20 "${ROUDI_LOG}" >&2 || true
    rm -f "${ROUDI_PIDFILE}"
    exit 1
  fi
}

case "${ACTION}" in
  start) do_start ;;
  stop) do_stop ;;
  status) do_status ;;
  *)
    echo "Usage: $0 [start|stop|status]" >&2
    exit 1
    ;;
esac
