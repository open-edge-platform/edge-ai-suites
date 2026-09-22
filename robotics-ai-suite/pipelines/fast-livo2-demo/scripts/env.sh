#!/usr/bin/env bash
# Central configuration for the FAST-LIVO2 demo scripts.
#
# Edit the variables below to retarget paths, the ROS distro, or the dataset
# sequence under test. Every other script in this directory sources this file
# and only this file - there is nothing else to edit to reproduce results on
# a different machine or with a different NTU VIRAL sequence.

# Directory this file lives in, and the demo pipeline root (one level up).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ROS 2 distro to build and run against. FAST-LIVO2/README_ROS2.md is
# validated on Humble and Jazzy; Jazzy on Ubuntu 24.04 is the primary target.
ROS_DISTRO="${ROS_DISTRO:-jazzy}"

# DDS network isolation. fastlivo_mapping, `ros2 bag play`, and rviz2 only
# see each other's topics if they agree on both of these - unlike every
# other variable in this file, they must be actually exported (not just set)
# since ROS 2 reads them from each process's own environment at init, and
# forked children (rviz2 via taskset, the algorithm/bag-play via
# run_ntu_viral.sh's ptl_wrap()) only inherit exported vars. Tracked here
# rather than left to a personal ~/.bashrc so a fresh checkout on a new
# machine isolates from other ROS 2 traffic on the same LAN by default
# (domain 0 is the default everyone else uses too) instead of silently
# picking up - or colliding with - unrelated publishers.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-199}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"

# Optional production-equivalent CycloneDDS + iceoryx shared-memory transport
# (see scripts/setup_dds_shm.sh and README.md "Optional: production-equivalent
# CycloneDDS + iceoryx shared-memory setup"). On by default so
# reproduce_all.sh exercises the same DDS path as Bing's own benchmark
# scripts; set to "false" to run on plain CycloneDDS with no SHM (still
# works, just without zero-copy same-host transport). Not exported: only
# run_ntu_viral.sh acts on it, and CYCLONEDDS_URI itself is set there (not
# here), since it must only point at the generated xml once
# setup_dds_shm.sh has actually created it.
USE_DDS_SHM="${USE_DDS_SHM:-true}"

DDS_SHM_DIR="${SCRIPT_DIR}/generated"
CYCLONEDDS_SHM_XML="${DDS_SHM_DIR}/cyclonedds_shm.xml"
ROUDI_CONFIG="${DDS_SHM_DIR}/roudi_config.toml"
ROUDI_PIDFILE="${DDS_SHM_DIR}/roudi.pid"
ROUDI_LOG="${DDS_SHM_DIR}/roudi.log"

# Path to the FAST-LIVO2 submodule. Patches are applied in place here.
FASTLIVO2_SRC="${DEMO_DIR}/FAST-LIVO2"

# Colcon workspace used to build fast_livo2, kept outside the submodule so
# build/install/log directories never collide with the patched git checkout.
WS_DIR="${WS_DIR:-${HOME}/fast_livo2_ws}"

# Cache directory for one-time source builds (Livox-SDK2, Sophus, vikit).
BUILD_CACHE="${BUILD_CACHE:-${HOME}/.cache/fast_livo2_deps}"

# Path to an existing workspace install space that already provides
# livox_ros_driver2 and vikit_ros (e.g. built once and reused across
# checkouts). Leave empty to have scripts/build.sh build them from scratch
# into $WS_DIR instead.
UNDERLAY_SETUP="${UNDERLAY_SETUP:-}"

# Build fast_livo2 with the per-frame LIO/VIO timing CSV export (adds a
# fopen/fprintf per frame; see CMakeLists.txt). Off by default.
ENABLE_PERFRAME_TIMING="${ENABLE_PERFRAME_TIMING:-OFF}"

# NTU VIRAL sequence used for the no-hardware validation flow.
# https://ntu-aris.github.io/ntu_viral_dataset/
NTU_VIRAL_SEQUENCE="${NTU_VIRAL_SEQUENCE:-eee_01}"

# Launch rviz2 alongside fast_livo2 in run_ntu_viral.sh. Off by default
# so the flow stays headless over SSH; set to "true" only when running
# directly on a machine with a display (rviz2's point-cloud rendering over
# X11 forwarding is impractical).
USE_RVIZ="${USE_RVIZ:-false}"

# Where the downloaded/converted dataset and ground truth live.
DATASET_DIR="${DATASET_DIR:-${HOME}/ntu_viral_dataset}"

# How far above the documented baseline a freshly measured RMSE may land
# (as a percentage of the baseline) and still count as a pass in
# scripts/evaluate_rmse.sh. Not a tuned statistical bound - just wide enough
# to absorb normal run-to-run non-determinism (thread scheduling, sensor
# timestamp jitter) without masking a real regression. A measurement at or
# below the baseline always passes; there is no lower bound.
RMSE_TOLERANCE_PCT="${RMSE_TOLERANCE_PCT:-20}"

# Expected RMSE (cm), per sequence, as measured and documented in
# FAST-LIVO2/Log/result/ntu_viral/README.md. scripts/evaluate_rmse.sh
# compares the freshly measured RMSE against this baseline: it passes when
# it does not exceed the baseline by more than RMSE_TOLERANCE_PCT%.
expected_rmse_cm() {
  case "$1" in
    eee_01) echo "2.71" ;;
    eee_02) echo "2.11" ;;
    eee_03) echo "2.61" ;;
    nya_01) echo "3.56" ;;
    nya_02) echo "3.39" ;;
    nya_03) echo "3.52" ;;
    sbs_01) echo "2.34" ;;
    sbs_02) echo "2.83" ;;
    sbs_03) echo "3.11" ;;
    *) echo "unknown" ;;
  esac
}

# NTU Dataverse file id for each sequence's raw-data zip (contains the ROS1
# .bag). Looked up from the dataset record doi:10.21979/N9/X39LEK and fetched
# via its public REST API, no login required:
#   https://researchdata.ntu.edu.sg/api/access/datafile/<id>
ntu_viral_datafile_id() {
  case "$1" in
    eee_01) echo "68133" ;;
    eee_02) echo "68131" ;;
    eee_03) echo "68132" ;;
    nya_01) echo "68144" ;;
    nya_02) echo "68138" ;;
    nya_03) echo "68142" ;;
    sbs_01) echo "68139" ;;
    sbs_02) echo "68140" ;;
    sbs_03) echo "68143" ;;
    *) echo "" ;;
  esac
}

# Per-task CPU affinity for PTL (Intel Core Ultra X7 358H).
# P-core    (Lion Cove): cpu 0-3   (up to 4700 MHz)
# E-core    (Skymont):   cpu 4-11  (up to 3500 MHz)
# LP-E-core (Skymont):   cpu 12-15 (up to 3300 MHz)
# Core numbering is specific to this SKU - re-check `lscpu -e` before
# reusing these defaults on a different PTL SKU or platform.
#
# run_ntu_viral.sh wraps each task with `taskset -c` (and, best-effort,
# `sudo -n chrt -f 85` realtime priority for the algorithm and bag play)
# whenever its variable below is non-empty. Leave a variable empty
# (e.g. CPUSET_ALGO="") to run that task unpinned.
CPUSET_ALGO="${CPUSET_ALGO:-12,13}"   # FAST-LIVO2 algorithm - isolated LP-E cores
CPUSET_BAG="${CPUSET_BAG:-1}"         # ros2 bag play (bag replay) - dedicated P-core
CPUSET_RVIZ="${CPUSET_RVIZ:-2}"       # rviz2 visualization - dedicated P-core

# CPU frequency locking for apples-to-apples PTL benchmarking, applied by
# scripts/limit_ptl_cores.sh (run once, with sudo, before benchmarking).
# Sets governor + min=max frequency per core cluster via sysfs cpufreq,
# then reinforces the max with a direct HWP MSR write.
FREQ_P_CORES="${FREQ_P_CORES:-0 1 2 3}"
FREQ_E_CORES="${FREQ_E_CORES:-4 5 6 7 8 9 10 11}"
FREQ_LPE_CORES="${FREQ_LPE_CORES:-12 13 14 15}"
FREQ_P_MAX="${FREQ_P_MAX:-4700000}"      # kHz; MIN=MAX locks the frequency
FREQ_P_MIN="${FREQ_P_MIN:-4700000}"
FREQ_E_MAX="${FREQ_E_MAX:-3500000}"
FREQ_E_MIN="${FREQ_E_MIN:-3500000}"
FREQ_LPE_MAX="${FREQ_LPE_MAX:-3300000}"
FREQ_LPE_MIN="${FREQ_LPE_MIN:-3300000}"
CPU_MODE_P="${CPU_MODE_P:-performance}"
CPU_MODE_E="${CPU_MODE_E:-performance}"  # governor for E/LP-E cores (cpu4-15)
