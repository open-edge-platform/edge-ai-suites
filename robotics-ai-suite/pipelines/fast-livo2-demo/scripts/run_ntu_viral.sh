#!/usr/bin/env bash
# Launch fast_livo2 on the configured NTU VIRAL sequence and play back the
# converted ROS 2 bag. Produces a TUM-format trajectory at
# FAST-LIVO2/Log/result/<sequence>.txt (consumed by evaluate_rmse.sh).
#
# Usage: ./run_ntu_viral.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SEQ="${NTU_VIRAL_SEQUENCE}"
BAG_ROS2="${DATASET_DIR}/${SEQ}"

if [[ ! -d "${BAG_ROS2}" ]]; then
  echo "Converted bag not found at ${BAG_ROS2}. Run ./fetch_ntu_viral.sh first." >&2
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
# order (rather than chaining `chrt -f 85 taskset ... exec <cmd>` as one
# root-owned command line, as an earlier version of this script did) is
# deliberate: a root-owned fast_livo2 process cannot register with an
# iceoryx RouDi daemon started by the invoking (non-root) user - RouDi's
# Unix-domain registration socket creation is rejected across that UID
# boundary ("permission to create unix domain socket denied" in RouDi's own
# log), which iceoryx surfaces as a fatal "Timeout registering at RouDi. Is
# RouDi running?" and aborts the process. Keeping <cmd...> running as the
# invoking user the whole time avoids that boundary entirely, and - as a
# bonus - it inherits this script's exported environment
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
    if ! sudo -n chrt -f -a -p 85 "${PTL_LAST_PID}" 2>/dev/null; then
      echo "WARN: 'sudo -n chrt -a -p' unavailable (no NOPASSWD sudoers entry for chrt) - running pinned to cpu ${cpuset} without realtime priority" >&2
    fi
  fi
}

# ptl_pid_tree <pid> - print <pid> and all of its descendants (recursive,
# via `pgrep -P`), one per line. Some launched tools (e.g. `ros2 launch`)
# spawn the real binary as a SEPARATE child via subprocess rather than exec
# - a signal to the top PID alone never reaches that grandchild, which is
# then orphaned (reparented to pid 1) and keeps running, holding this
# script's stdout/stderr pipe open forever. Walk the whole tree so cleanup
# actually terminates every process a wrapped command started, not just its
# wrapper.
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
  # Pre-increment: post-increment's `(( waited++ ))` evaluates to the
  # pre-increment value, which is 0 on the first pass - under `set -e` a
  # standalone `(( expr ))` that evaluates to 0 counts as command failure
  # and would abort the whole script right here.
  while ptl_pid_alive "${pid}" && (( waited < limit )); do
    sleep 0.1
    (( ++waited ))
  done
  ! ptl_pid_alive "${pid}"
}

# Send SIGTERM to `pid`, wait up to ~10s for it to exit, escalate to
# SIGKILL and wait up to ~5s more, then reap it. Every wait is bounded by
# ptl_wait_dead's polling (never a blocking `wait`) so a process this
# script genuinely cannot signal logs a warning instead of hanging the
# script forever the way the old plain-`kill`-then-`wait` trap did.
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

mkdir -p "${FASTLIVO2_SRC}/Log/result"
RESULT_FILE="${FASTLIVO2_SRC}/Log/result/${SEQ}.txt"
rm -f "${RESULT_FILE}"

# NTU_VIRAL.yaml defaults evo/seq_name to "eee_01"; point it at the
# configured sequence via a scratch copy instead of editing the tracked file.
PARAMS_FILE="$(mktemp --suffix=.yaml)"
sed "s/seq_name: \"eee_01\"/seq_name: \"${SEQ}\"/" \
  "${FASTLIVO2_SRC}/config/NTU_VIRAL.yaml" > "${PARAMS_FILE}"

echo "==> Launching fast_livo2 for sequence ${SEQ}"
# rviz2 is always launched (if at all) as its own process below, never via
# use_rviz:=true here - that would spawn it as a child Node inside this same
# ros2 launch process, inheriting fast_livo2's own taskset affinity with no
# way to give it CPUSET_RVIZ independently. See README.md "Reference:
# running on Intel PTL".
ptl_wrap "${CPUSET_ALGO}" 1 \
  ros2 launch fast_livo2 mapping_ouster_ntu.launch.py \
  use_rviz:=false \
  avia_params_file:="${PARAMS_FILE}"
LIVO_PID="${PTL_LAST_PID}"
RVIZ_PID=""
BAG_PID=""
# Always stop fast_livo2 (and rviz2/bag play, if started) and clean up the
# scratch params file on exit, even if a step below fails - otherwise (with
# `set -e`) this script would abort before reaching this cleanup, leaving
# processes running as orphans that keep stdout (and any pipe/tee reading
# it, e.g. from sync_and_verify_ptl.sh) open forever. RVIZ_PID/BAG_PID are
# pre-declared above so an interruption before they're assigned doesn't
# trip `set -u` here. Goes through ptl_stop (whole-process-tree-aware kill
# + bounded wait + SIGKILL escalation, see ptl_pid_tree above) rather than
# a plain `kill`/`wait` pair - some launched tools spawn their real binary
# as a separate child rather than exec'ing it, which a plain `kill`/`wait`
# on just the top PID would leave running as an orphan.
cleanup() {
  ptl_stop "${LIVO_PID}"
  ptl_stop "${RVIZ_PID}"
  ptl_stop "${BAG_PID}"
  rm -f "${PARAMS_FILE}"
}
trap cleanup EXIT

if [[ "${USE_RVIZ}" == "true" ]]; then
  echo "==> Launching rviz2"
  # No SCHED_FIFO here (rt=0): rviz2 is GUI/rendering work off the timing
  # -critical path; priority-85 FIFO on a process that can block on GL/X11
  # calls risks starving other tasks on its core. taskset pinning alone is
  # enough to keep it off the algorithm's isolated cores.
  ptl_wrap "${CPUSET_RVIZ}" 0 rviz2 -d "${FASTLIVO2_SRC}/rviz_cfg/ntu_viral.rviz"
  RVIZ_PID="${PTL_LAST_PID}"
fi

sleep 5
echo "==> Playing back ${BAG_ROS2}"
ptl_wrap "${CPUSET_BAG}" 1 ros2 bag play "${BAG_ROS2}"
BAG_PID="${PTL_LAST_PID}"
wait "${BAG_PID}"

echo "==> Bag playback finished, stopping fast_livo2"

if [[ -s "${RESULT_FILE}" ]]; then
  echo "==> Trajectory written to ${RESULT_FILE}"
else
  echo "No trajectory written to ${RESULT_FILE} - check the fast_livo2 log output above." >&2
  exit 1
fi
