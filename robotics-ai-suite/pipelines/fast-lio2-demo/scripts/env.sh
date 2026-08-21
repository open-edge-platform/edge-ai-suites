#!/usr/bin/env bash
# Central configuration for the FAST-LIO2 demo scripts.
#
# Edit the variables below to retarget paths, the ROS distro, or the
# UrbanLoco sequence under test. Every other script in this directory
# sources this file and only this file - there is nothing else to edit to
# reproduce results on a different machine or with a different sequence.

# Directory this file lives in, and the demo pipeline root (one level up).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ROS 2 distro to build and run against. Jazzy on Ubuntu 24.04 is the
# primary/only validated target for this pipeline.
ROS_DISTRO="${ROS_DISTRO:-jazzy}"

# DDS network isolation. fastlio_mapping, the UrbanLoco bag publisher, and
# rviz2 only see each other's topics if they agree on both of these - unlike
# every other variable in this file, they must be actually exported (not
# just set) since ROS 2 reads them from each process's own environment at
# init, and forked children (rviz2 via taskset, the algorithm/publisher via
# run_ulhk.sh's ptl_wrap()) only inherit exported vars. Tracked here rather
# than left to a personal ~/.bashrc so a fresh checkout on a new machine
# isolates from other ROS 2 traffic on the same LAN by default (domain 0 is
# the default everyone else uses too) instead of silently picking up - or
# colliding with - unrelated publishers.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-199}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"

# Optional production-equivalent CycloneDDS + iceoryx shared-memory transport
# (see scripts/setup_dds_shm.sh and README.md "Optional: production-equivalent
# CycloneDDS + iceoryx shared-memory setup"). On by default so
# reproduce_all.sh exercises the same DDS path as Bing's own benchmark
# scripts; set to "false" to run on plain CycloneDDS with no SHM (still
# works, just without zero-copy same-host transport). Not exported: only
# run_ulhk.sh acts on it, and CYCLONEDDS_URI itself is set there (not here),
# since it must only point at the generated xml once setup_dds_shm.sh has
# actually created it.
USE_DDS_SHM="${USE_DDS_SHM:-true}"

DDS_SHM_DIR="${SCRIPT_DIR}/generated"
CYCLONEDDS_SHM_XML="${DDS_SHM_DIR}/cyclonedds_shm.xml"
ROUDI_CONFIG="${DDS_SHM_DIR}/roudi_config.toml"
ROUDI_PIDFILE="${DDS_SHM_DIR}/roudi.pid"
ROUDI_LOG="${DDS_SHM_DIR}/roudi.log"

# Path to the FAST_LIO submodule. Patches are applied in place here.
FASTLIO_SRC="${DEMO_DIR}/FAST_LIO"

# Colcon workspace used to build fast_lio, kept outside the submodule so
# build/install/log directories never collide with the patched git checkout.
WS_DIR="${WS_DIR:-${HOME}/fast_lio2_ws}"

# Cache directory for one-time source builds (Livox-SDK2).
BUILD_CACHE="${BUILD_CACHE:-${HOME}/.cache/fast_lio2_deps}"

# Tag of the livox_ros_driver2 package fast_lio's CMakeLists.txt/package.xml
# unconditionally depend on, even though this pipeline only ever validates
# against Velodyne data - see README.md "Intel contributions" / limitations.
LIVOX_DRIVER_TAG="${LIVOX_DRIVER_TAG:-1.2.6}"

# Build fast_lio with the CSV latency-profiling instrumentation (adds a
# ring-buffer + dedicated writer thread; see patch 0001 and CMakeLists.txt's
# ENABLE_PROFILING option). Off by default, matching upstream's own default.
ENABLE_PROFILING="${ENABLE_PROFILING:-OFF}"

# UrbanLoco sequence used for the no-hardware validation flow. Sequence name
# follows the FAST-LIO2/Point-LIO papers' own internal benchmark naming
# (FAST-LIO2: Xu et al. 2022, IEEE T-RO, arXiv 2107.06829, Table II/IV;
# Point-LIO: He et al. 2023, Advanced Intelligent Systems, Table 5) - only
# ulhk_4 is fully wired up below (confirmed date + documented baseline);
# ulhk_5/ulhk_6 are left as an extension point, not populated with
# unconfirmed guesses.
ULHK_SEQUENCE="${ULHK_SEQUENCE:-ulhk_4}"

# UrbanLoco session name (the dataset's own on-disk naming) for each
# sequence - see README.md "Validate without hardware", official source:
# github.com/weisongwen/UrbanLoco, section "2. Hong Kong Dataset".
ulhk_session_name() {
  case "$1" in
    ulhk_4) echo "HK-Data20190117" ;;
    *) echo "" ;;
  esac
}

# Launch rviz2 alongside fast_lio in run_ulhk.sh. Off by default so the flow
# stays headless over SSH; set to "true" only when running directly on a
# machine with a display (rviz2's point-cloud rendering over X11 forwarding
# is impractical).
USE_RVIZ="${USE_RVIZ:-false}"

# Where the downloaded UrbanLoco file and generated results live.
# Deliberately repo-relative and .gitignore'd (not $HOME) so placing a
# downloaded dataset here is a single obvious step for anyone cloning this
# repo; override to point at a shared/pre-populated location instead.
DATASET_DIR="${DATASET_DIR:-${DEMO_DIR}/datasets/${ULHK_SEQUENCE}}"
RESULTS_DIR="${RESULTS_DIR:-${DATASET_DIR}/results}"

# Raw file placed by hand per fetch_ulhk.sh's instructions (may be a ROS1
# bag or already a ROS2 bag - convert_ulhk_to_bag.sh inspects it and
# converts only if needed) and the ROS 2 bag directory run_ulhk.sh replays.
# sqlite3 is the storage plugin ROS 2's own rosbag2 package always ships
# with (no extra apt package needed); override BAG_STORAGE_ID to "mcap" if
# that plugin is installed and preferred.
ULHK_RAW_FILE="${ULHK_RAW_FILE:-${DATASET_DIR}/$(ulhk_session_name "${ULHK_SEQUENCE}").bag}"
BAG_DIR="${BAG_DIR:-${DATASET_DIR}/ulhk_bag}"
BAG_STORAGE_ID="${BAG_STORAGE_ID:-sqlite3}"

# Topics inside the converted bag - the pristine upstream config/velodyne.yaml
# defaults to "/velodyne_points"/pcd_save_en:true, so run_ulhk.sh overrides
# both of these (plus pcd_save_en) at the `ros2 run` level via `-p` instead.
# No FAST_LIO source/config change is needed for this dataset.
ULHK_LIDAR_TOPIC="${ULHK_LIDAR_TOPIC:-/velodyne_points_0}"
ULHK_IMU_TOPIC="${ULHK_IMU_TOPIC:-/imu/data}"
# NovAtel SPAN-CPT INSPVAX ground-truth messages (geodetic lat/lon/hgt),
# read directly out of the bag's .db3 by extract_ulhk_gt.py - see that
# script for the CDR field-offset parsing and geodetic->ENU conversion.
ULHK_GT_TOPIC="${ULHK_GT_TOPIC:-/novatel_data/inspvax}"

# How far a freshly measured RMSE may drift from the documented baseline
# (as a percentage of the baseline) and still count as a pass in
# scripts/evaluate_rmse.sh. Not a tuned statistical bound - just wide enough
# to absorb normal run-to-run non-determinism (thread scheduling, sensor
# timestamp jitter) without masking a real regression.
RMSE_TOLERANCE_PCT="${RMSE_TOLERANCE_PCT:-20}"

# Optional: replay only a slice of the bag instead of the full sequence, for
# fast iteration (the full ulhk_4 bag is already short, ~5:21, but this is
# still useful for a quick smoke test). Both blank by default (full
# playback, unchanged behavior). Set PLAY_START_OFFSET_S to start partway
# into the bag (passed straight to `ros2 bag play --start-offset`) and/or
# PLAY_DURATION_S to stop playback after that many (real, wall-clock)
# seconds instead of waiting for EOF. scripts/evaluate_rmse.sh skips the
# baseline PASS/FAIL check whenever either is set, since the documented
# baseline below is for the full sequence only.
PLAY_START_OFFSET_S="${PLAY_START_OFFSET_S:-}"
PLAY_DURATION_S="${PLAY_DURATION_S:-}"

# Expected RMSE (meters), per sequence. Primary citation for ulhk_4 (this is
# the FAST-LIO2 repo): FAST-LIO2 paper (Xu et al. 2022, IEEE T-RO, arXiv
# 2107.06829), Table IV, "Absolute Translational Errors (RMSE, meters) in
# Sequences with Good Quality Ground Truth" - 2.57 m, constant across all
# four non-feature map sizes tested there (2000/1000/800/600m; the
# feature-based variant gets 2.29 m). Point-LIO's own paper (He et al. 2023,
# Advanced Intelligent Systems, DOI 10.1002/aisy.202200459, Table 5) reports
# 2.17 m on the same sequence - printed alongside for context only, not
# compared against. Intel's own reproduce_all.sh run on the PTL board has
# separately measured 1.327 m on this exact sequence, comfortably inside the
# tolerance band below. scripts/evaluate_rmse.sh compares the freshly
# measured RMSE against the FAST-LIO2 baseline within +RMSE_TOLERANCE_PCT%
# (one-sided: any measured value at or below the baseline always passes).
expected_rmse_m() {
  case "$1" in
    ulhk_4) echo "2.57" ;;
    *) echo "unknown" ;;
  esac
}

# Per-task CPU affinity for PTL (Intel Core Ultra X7 358H).
# P-core    (Lion Cove): cpu 0-3   (up to 4700 MHz)
# E-core    (Skymont):   cpu 4-11  (up to 3500 MHz)
# LP-E-core (Skymont):   cpu 12-15 (up to 3300 MHz)
# Core numbering is specific to this SKU - re-check `lscpu -e` before
# reusing these defaults on a different PTL SKU or platform.
#
# run_ulhk.sh wraps each task with `taskset -c` (and, best-effort,
# `sudo -n chrt -f 85` realtime priority for the algorithm and the dataset
# publisher) whenever its variable below is non-empty. Leave a variable
# empty (e.g. CPUSET_ALGO="") to run that task unpinned.
CPUSET_ALGO="${CPUSET_ALGO:-12,13}"   # fastlio_mapping algorithm - isolated LP-E cores
CPUSET_BAG="${CPUSET_BAG:-1}"         # `ros2 bag play` of the converted UrbanLoco bag - dedicated P-core
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
