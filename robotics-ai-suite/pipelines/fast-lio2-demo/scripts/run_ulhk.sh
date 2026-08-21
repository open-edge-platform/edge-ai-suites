#!/usr/bin/env bash
# Launch fastlio_mapping on the configured UrbanLoco sequence and replay it
# via `ros2 bag play` against the bag scripts/convert_ulhk_to_bag.sh
# produced.
# Produces an estimated trajectory at ${RESULTS_DIR}/<sequence>_est_tum.txt
# (via record_odometry_tum.py, consumed by evaluate_rmse.sh).
#
# Usage: ./run_ulhk.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SEQ="${ULHK_SEQUENCE}"

if [[ ! -d "${BAG_DIR}" ]]; then
  echo "No converted bag at ${BAG_DIR}. Run ./convert_ulhk_to_bag.sh first." >&2
  exit 1
fi

# Switch to the CycloneDDS+iceoryx shared-memory transport setup_dds_shm.sh
# generates, if it's actually up - warn-and-continue on plain CycloneDDS
# (env.sh's default RMW, no SHM) otherwise, same as the sudo -n fallback
# further down; this never blocks a run.
if [[ "${USE_DDS_SHM}" == "true" ]]; then
  if [[ -f "${CYCLONEDDS_SHM_XML}" ]] && pgrep -x iox-roudi >/dev/null 2>&1; then
    export CYCLONEDDS_URI="file://${CYCLONEDDS_SHM_XML}"
  else
    echo "WARN: USE_DDS_SHM=true but no running iox-roudi/generated config found - run ./setup_dds_shm.sh first. Continuing on plain CycloneDDS (no shared memory)." >&2
  fi
fi

# ROS 2's setup.bash references internal ament/colcon trace variables that
# are never exported with a default, so it's incompatible with `set -u`;
# disable nounset just around sourcing it.
set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source "${WS_DIR}/install/setup.bash"
set -u

# ptl_wrap <cpuset> <rt:0|1> <cmd...>
# Backgrounds "<cmd...>" as the invoking (non-root) user, pinned to CPU list
# <cpuset> via taskset (skipped if <cpuset> is empty), and - only when <rt>
# is 1 - best-effort reprioritized to SCHED_FIFO 85 via `sudo -n chrt -f -a
# -p 85 <pid>` AFTER it's already running. This launch-then-reprioritize
# order is deliberate: a root-owned fastlio_mapping process cannot register
# with an iceoryx RouDi daemon started by the invoking (non-root) user -
# RouDi's Unix-domain registration socket creation is rejected across that
# UID boundary, which iceoryx surfaces as a fatal "Timeout registering at
# RouDi. Is RouDi running?" and aborts the process. Keeping <cmd...> running
# as the invoking user the whole time avoids that boundary entirely, and -
# as a bonus - it inherits this script's exported environment
# (ROS_DOMAIN_ID/RMW_IMPLEMENTATION/CYCLONEDDS_URI included) exactly as-is,
# with no re-export/re-source dance needed. `-a`/`--all-tasks` applies the
# priority to every thread of the target pid, not just its main thread -
# required since ROS 2 executors are multi-threaded.
# Sets PTL_LAST_PID (a `pid=$(ptl_wrap ...)` return would lose the
# background job to a subshell, since command substitution runs in one).
ptl_wrap() {
  local cpuset="$1" rt="$2"; shift 2
  if [[ -z "${cpuset}" ]]; then
    "$@" &
  else
    taskset -c "${cpuset}" "$@" &
  fi
  PTL_LAST_PID=$!
  if [[ "${rt}" == "1" ]]; then
    # Some wrapper CLIs (e.g. `ros2 run`) subprocess.Popen() the real binary
    # as a SEPARATE child rather than exec()'ing into it, so chrt on
    # PTL_LAST_PID alone would only ever reprioritize the idle Python
    # wrapper - never the actual workload - leaving it at plain CFS
    # priority for the whole run. Give it a moment to actually fork, then
    # walk the whole descendant tree (ptl_pid_tree, defined below -
    # available by the time this runs) and reprioritize every PID in it,
    # not just the top one.
    local tries=0
    while [[ -z "$(pgrep -P "${PTL_LAST_PID}" 2>/dev/null)" && "${tries}" -lt 20 ]]; do
      sleep 0.05
      (( ++tries ))
    done
    local pid all_ok=true
    for pid in $(ptl_pid_tree "${PTL_LAST_PID}"); do
      sudo -n chrt -f -a -p 85 "${pid}" 2>/dev/null || all_ok=false
    done
    "${all_ok}" || echo "WARN: 'sudo -n chrt -a -p' unavailable (no NOPASSWD sudoers entry for chrt) - running pinned to cpu ${cpuset} without realtime priority" >&2
  fi
}

# ptl_pid_tree <pid> - print <pid> and all of its descendants (recursive,
# via `pgrep -P`), one per line. Some launched tools (e.g. `ros2 run`) spawn
# the real binary as a SEPARATE child via subprocess rather than exec - a
# signal to the top PID alone never reaches that grandchild, which is then
# orphaned (reparented to pid 1) and keeps running. Walk the whole tree so
# cleanup actually terminates every process a wrapped command started, not
# just its wrapper.
ptl_pid_tree() {
  local pid="$1" child
  echo "${pid}"
  for child in $(pgrep -P "${pid}" 2>/dev/null); do
    ptl_pid_tree "${child}"
  done
}

# Signal `pid` and all its descendants. Every process ptl_wrap launches
# stays owned by the invoking (non-root) user (see ptl_wrap above) - only
# its scheduling priority is elevated via sudo, not its UID - so a plain
# `kill` from this unprivileged script always works here, no `sudo -n`
# fallback needed.
ptl_kill() {
  local pid="$1" sig="$2" p
  for p in $(ptl_pid_tree "${pid}"); do
    kill "-${sig}" "${p}" 2>/dev/null || true
  done
}

ptl_pid_alive() {
  local pid="$1" p
  for p in $(ptl_pid_tree "${pid}"); do
    kill -0 "${p}" 2>/dev/null && return 0
  done
  return 1
}

# ptl_wait_dead <pid> <max tenths-of-a-second> - poll ptl_pid_alive rather
# than blocking on it, so a stuck process bounds this to a fixed timeout
# instead of hanging forever.
ptl_wait_dead() {
  local pid="$1" limit="$2" waited=0
  while ptl_pid_alive "${pid}" && (( waited < limit )); do
    sleep 0.1
    (( ++waited ))
  done
  ! ptl_pid_alive "${pid}"
}

# Send SIGTERM to `pid`, wait up to ~10s for it to exit, escalate to
# SIGKILL and wait up to ~5s more, then reap it.
ptl_stop() {
  local pid="$1"
  [[ -z "${pid}" ]] && return 0
  ptl_kill "${pid}" TERM
  ptl_wait_dead "${pid}" 100 && { wait "${pid}" 2>/dev/null || true; return 0; }
  ptl_kill "${pid}" KILL
  if ptl_wait_dead "${pid}" 50; then
    wait "${pid}" 2>/dev/null || true
  else
    echo "WARN: could not stop pid ${pid}" >&2
  fi
}

# A prior run of this script can leave fastlio_mapping/ros2 bag play/the
# recorder running as orphans if it was killed hard enough that its own
# `cleanup` trap below never got to run (e.g. the controlling SSH/pty
# session dropped mid-run). Clear out anything matching this pipeline's own
# process signatures before launching a fresh run, rather than starting
# alongside a leftover one.
echo "==> Cleaning up any leftover processes from a previous run"
pkill -f "ros2 run fast_lio fastlio_mapping" 2>/dev/null || true
pkill -f "ros2 bag play ${BAG_DIR}" 2>/dev/null || true
pkill -f "record_odometry_tum.py --topic /Odometry" 2>/dev/null || true
sleep 1

mkdir -p "${RESULTS_DIR}"
RESULT_FILE="${RESULTS_DIR}/${SEQ}_est_tum.txt"
rm -f "${RESULT_FILE}"

CONFIG_PATH="${WS_DIR}/install/fast_lio/share/fast_lio/config"
# The pristine upstream velodyne.yaml already has the right LiDAR/IMU
# parameters for UrbanLoco's Velodyne HDL-32E + external IMU rig (scan_line
# 32, scan_rate 10, timestamp_unit 2, blind 2.0, extrinsic_T [0,0,0.28],
# identity extrinsic_R - the same values point-lio's own
# velodyne_urbanloco.yaml uses for the same physical rig) - no Intel patch
# or new config file needed for this dataset. Only the topic names and
# pcd_save_en differ from its defaults, overridden below at the `ros2 run`
# level via `-p` instead.
CONFIG_FILE="velodyne.yaml"

echo "==> Launching fastlio_mapping for sequence ${SEQ}"
# rviz2 is always launched (if at all) as its own process below, so it never
# inherits fastlio_mapping's own taskset affinity. See README.md "Reference:
# running on Intel PTL".
ptl_wrap "${CPUSET_ALGO}" 1 \
  ros2 run fast_lio fastlio_mapping --ros-args \
  --params-file "${CONFIG_PATH}/${CONFIG_FILE}" \
  -p "common.lid_topic:=${ULHK_LIDAR_TOPIC}" \
  -p "common.imu_topic:=${ULHK_IMU_TOPIC}" \
  -p "pcd_save.pcd_save_en:=false" \
  -p "use_sim_time:=false"
ALGO_PID="${PTL_LAST_PID}"
RVIZ_PID=""
PUB_PID=""
REC_PID=""

# Always stop every process and remove nothing (no scratch files here) on
# exit, even if a step below fails - otherwise (with `set -e`) this script
# would abort before reaching cleanup, leaving processes running as
# orphans. Goes through ptl_stop (bounded wait + SIGKILL escalation, whole
# process-tree aware - see ptl_pid_tree above).
cleanup() {
  ptl_stop "${ALGO_PID}"
  ptl_stop "${REC_PID}"
  ptl_stop "${RVIZ_PID}"
  ptl_stop "${PUB_PID}"
}
trap cleanup EXIT

echo "==> Recording /Odometry to ${RESULT_FILE}"
python3 "${SCRIPT_DIR}/record_odometry_tum.py" --topic /Odometry --out "${RESULT_FILE}" &
REC_PID=$!

if [[ "${USE_RVIZ}" == "true" ]]; then
  echo "==> Launching rviz2"
  # No SCHED_FIFO here (rt=0): rviz2 is GUI/rendering work off the timing
  # -critical path; priority-85 FIFO on a process that can block on GL/X11
  # calls risks starving other tasks on its core.
  ptl_wrap "${CPUSET_RVIZ}" 0 rviz2 -d "${FASTLIO_SRC}/rviz/fastlio.rviz"
  RVIZ_PID="${PTL_LAST_PID}"
fi

sleep 5
echo "==> Playing back UrbanLoco ${SEQ} bag from ${BAG_DIR}"
echo "==> NOTE: fastlio_mapping will repeat \"Failed to find match for field 'time'.\" once per"
echo "    scan for the whole run below - expected/harmless (UrbanLoco's velodyne points have no"
echo "    per-point timestamp; see README.md \"Validate without hardware\"), not a sign of a problem."
# `ros2 bag play` replays at ~1x recorded speed and this script blocks on
# it until playback finishes, so print the bag's own recorded duration up
# front - otherwise this produces no further log output until playback
# ends, which looks stuck rather than just replaying in real time.
BAG_DURATION="$(ros2 bag info "${BAG_DIR}" 2>/dev/null | sed -n 's/^ *Duration: *//p')"
PLAY_ARGS=()
if [[ -n "${PLAY_START_OFFSET_S}" ]]; then
  PLAY_ARGS+=(--start-offset "${PLAY_START_OFFSET_S}")
fi
if [[ -n "${PLAY_DURATION_S}" ]]; then
  echo "==> Bag duration: ${BAG_DURATION:-unknown}; playing a ${PLAY_DURATION_S}s slice starting at offset ${PLAY_START_OFFSET_S:-0}s (real time)."
else
  echo "==> Bag duration: ${BAG_DURATION:-unknown} - playback runs in real time, so expect roughly that long before the next log line."
fi
ptl_wrap "${CPUSET_BAG}" 1 \
  ros2 bag play "${BAG_DIR}" "${PLAY_ARGS[@]}"
PUB_PID="${PTL_LAST_PID}"
if [[ -n "${PLAY_DURATION_S}" ]]; then
  # Let it run for the requested slice, then stop it explicitly rather than
  # waiting for EOF - ptl_stop is a harmless no-op if playback already
  # finished on its own (e.g. slice longer than what's left in the bag).
  ptl_wait_dead "${PUB_PID}" $(( PLAY_DURATION_S * 10 )) || true
  ptl_stop "${PUB_PID}"
else
  wait "${PUB_PID}"
fi

echo "==> Playback finished, stopping fastlio_mapping"
sleep 2  # let the last odometry messages land before the recorder is stopped

if [[ -s "${RESULT_FILE}" ]]; then
  echo "==> Trajectory written to ${RESULT_FILE}"
else
  echo "No trajectory written to ${RESULT_FILE} - check the fastlio_mapping log output above." >&2
  exit 1
fi
