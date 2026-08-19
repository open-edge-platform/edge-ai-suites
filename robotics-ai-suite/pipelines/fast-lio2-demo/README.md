# LIO SLAM: FAST-LIO2

FAST-LIO2 is a computationally efficient, tightly-coupled LiDAR-Inertial
Odometry system built on an iterated Kalman filter and an incremental
ikd-Tree map, without explicit feature extraction.

![FAST-LIO2 system overview](https://raw.githubusercontent.com/hku-mars/FAST_LIO/main/doc/overview_fastlio2.svg)

- Paper: [FAST-LIO2: Fast Direct LiDAR-inertial Odometry](https://arxiv.org/abs/2107.06829) (IEEE T-RO / RA-L 2022)
- Upstream: [hku-mars/FAST_LIO](https://github.com/hku-mars/FAST_LIO) (`ROS2` branch)

In Robotics AI Suite, the upstream tree is a pristine git submodule and Intel
changes ship as patches on top, so FAST-LIO2 can be evaluated as an
alternative LIO backend without forking the reference navigation stack.

> [!IMPORTANT]
> FAST_LIO's [LICENSE](https://github.com/hku-mars/FAST_LIO/blob/a4743b095409588842a5b30ddfa27e29d2f99164/LICENSE) file is **GPLv2**. Its
> `package.xml` incorrectly declares `<license>BSD</license>` — that is
> upstream metadata, not the actual terms; treat this package as GPLv2 for
> compliance purposes. For commercial use, contact the upstream authors for
> an alternative license before shipping it in a product.

## Changes to 3rd party source

This work is based on the open-source
[FAST_LIO](https://github.com/hku-mars/FAST_LIO.git) repository (`ROS2`
branch), pinned in [.gitmodules](https://github.com/open-edge-platform/edge-ai-suites/blob/main/.gitmodules) at the upstream
commit the patch below applies to.

| Patch | Change |
| ----- | ------ |
| [0001-Add-profiling-instrumentation-new-LiDAR-configs-and-.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/patches/0001-Add-profiling-instrumentation-new-LiDAR-configs-and-.patch) | New Avia configs; `config/velodyne_generic.yaml` — a Velodyne HDL-32E parameter set for NCLT validation below, with the LiDAR-IMU extrinsic derived from the NCLT dataset paper's own Table 4 sensor calibration (not the UrbanLoco/Point-LIO placeholder it started from — see the comment above `extrinsic_T`/`extrinsic_R` in that file); C++17 + configurable OMP thread count in the build; a preprocess crash fix for Velodyne scans missing a `time` field; and a latency-profiling CSV (below). |

**Profiling**: built behind the `ENABLE_PROFILING` CMake option (off by
default, matching upstream). When enabled, a lock-free ring buffer plus a
dedicated writer thread records per-stage EKF timing (using
`CLOCK_MONOTONIC`, immune to PTP clock steps) to
`FAST_LIO/Log/fast_lio_profiling.csv`.

## Environment setup (Ubuntu 24.04 / ROS 2 Jazzy)

```bash
# 1. Fetch the pristine upstream submodule (--recursive also pulls in
# FAST_LIO's own nested ikd-Tree submodule, required by its CMakeLists.txt)
git submodule update --init --recursive robotics-ai-suite/pipelines/fast-lio2-demo/FAST_LIO

cd robotics-ai-suite/pipelines/fast-lio2-demo/scripts

# 2. One-time host dependencies (needs sudo; safe to re-run)
./install_deps.sh

# 3. Apply the Intel patches from the table above
./apply_patches.sh

# 4. Build fast_lio with colcon
./build.sh
```

All paths, the ROS distro, and the dataset sequence used below are
centralized in [scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/env.sh) — edit that one file to
retarget a different workspace/sequence; nothing else needs to change.

## Validate without hardware: NCLT dataset replay

No robot or sensor is required to verify the build and measure accuracy:
the `nclt_4` session (2012-01-15) from the public
[NCLT dataset](http://robots.engin.umich.edu/nclt/) (University of
Michigan) is replayed through `fastlio_mapping` and compared against its
SLAM-derived ground truth. NCLT is hosted directly over plain HTTP with no
access request or login — `fetch_nclt.sh` is a straight `wget`.

```bash
./fetch_nclt.sh           # download the Velodyne/IMU/ground-truth files (plain wget, no gating)
./convert_nclt_to_bag.sh  # one-time conversion of the raw files into a standard ROS 2 bag
./run_nclt.sh             # launch fastlio_mapping + `ros2 bag play` the converted bag, records the trajectory
./evaluate_rmse.sh        # evo_ape RMSE vs. ground truth, printed next to the documented baseline

# or, once install_deps.sh has been run once:
./reproduce_all.sh # apply patches -> build -> fetch -> convert -> run -> evaluate, in one command
```

NCLT's raw data isn't a plug-and-play rosbag (custom binary Velodyne format
+ CSV IMU); [scripts/convert_nclt_to_bag.py](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/convert_nclt_to_bag.py)
parses it once and writes a standard ROS 2 bag under `BAG_DIR`
([scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/env.sh)) — `convert_nclt_to_bag.sh` skips this
step on subsequent runs if that bag already exists (pass
`FORCE_CONVERT=true` to redo it). `run_nclt.sh` then replays that bag with
the standard `ros2 bag play`, like every other RAI-suite SLAM demo.

For `nclt_4`, the documented baseline is **8.6 m** RMSE (FAST-LIO2 paper,
arXiv 2107.06829, Table IV — consistent across all tested map sizes,
8.5–8.72 m). The check is one-sided: it passes as long as the freshly
measured RMSE does not exceed that baseline by more than
`RMSE_TOLERANCE_PCT` (20% by default) — a measured RMSE *lower* than the
baseline always passes, since the check exists to catch regressions, not to
flag outperforming the paper's own number.

### Fast iteration on a slice

The full `nclt_4` bag is ~112 minutes and `ros2 bag play` replays it in real
time (no fast-forward), so a full run takes roughly that long. For quicker
iteration, replay only part of the bag via
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/env.sh)'s `PLAY_START_OFFSET_S` /
`PLAY_DURATION_S`:

```bash
PLAY_START_OFFSET_S=0 PLAY_DURATION_S=180 ./run_nclt.sh   # ~3min smoke test
./evaluate_rmse.sh
```

`PLAY_START_OFFSET_S=0` (start from the beginning) is recommended over a
nonzero offset: FAST-LIO2 needs an IMU-init + map-convergence period right
at the start, so skipping ahead produces an unstable trajectory whose RMSE
isn't meaningful. `180s` is enough to get past that init and see a stable
odometry stream while staying fast; bump it toward 600–900s for a more
representative (but still partial) RMSE. `evaluate_rmse.sh` still prints the
measured RMSE for a sliced run but skips the PASS/FAIL check, since the
documented baseline above is for the full sequence only.

### Rviz visualization

`run_nclt.sh` gates `rviz2` behind the `USE_RVIZ` variable in
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/env.sh), off by default so the flow stays headless
over SSH:

```bash
USE_RVIZ=true ./run_nclt.sh   # or: USE_RVIZ=true ./reproduce_all.sh
```

Run this directly on the target machine's own logged-in Ubuntu desktop
session (e.g. on the PTL board's display, not over plain SSH) — rviz2's
point-cloud rendering needs a real GPU display, so X11-forwarding it over
SSH is impractical.

### Reference: running on Intel PTL

`run_nclt.sh` ships a reference core-pinning + frequency-locking setup for
Intel PTL (validated on Core Ultra X7 358H: 4 P-cores `cpu0-3` up to 4700
MHz, 8 E-cores `cpu4-11` up to 3500 MHz, 4 LP-E-cores `cpu12-15` up to 3300
MHz). Core numbering is specific to this SKU — re-check `lscpu -e` before
reusing these defaults on a different PTL SKU or platform.

| Task | Pinned to | Why |
| ---- | --------- | --- |
| `fastlio_mapping` algorithm | LP-E cores `12,13` (`CPUSET_ALGO`) | Keeps the timing-critical LIO thread on isolated cores the general scheduler and rest of the OS don't touch. |
| `ros2 bag play` of the converted NCLT bag | P-core `1` (`CPUSET_BAG`) | Replaying the pre-converted bag is bursty I/O + decode work; a dedicated P-core keeps it from stealing cycles from the algorithm cores. |
| `rviz2` (when `USE_RVIZ=true`) | P-core `2` (`CPUSET_RVIZ`) | Point-cloud rendering is bursty GUI work best kept off the algorithm's isolated cores; a P-core has the headroom for it. |

`run_nclt.sh` wraps the algorithm and `ros2 bag play` with `taskset -c` and,
best-effort, `sudo -n chrt -f -a -p 85 <pid>` SCHED_FIFO priority-85 —
applied to the process *after* it's already launched as the invoking
(non-root) user, not chained into the launch itself — whenever the matching
`CPUSET_*` variable in [scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/env.sh) is non-empty (the
default). `rviz2` gets `taskset` pinning only, no realtime priority. If
`sudo -n` isn't usable (no passwordless sudoers entry for `chrt`), the
script warns and continues unprioritized rather than failing the run. To
disable pinning for a given task, blank out its variable in `env.sh` (e.g.
`CPUSET_ALGO=""`).

Every process `run_nclt.sh` launches — including the RT-prioritized ones —
stays owned by the invoking user throughout, never root: `chrt -p <pid>`
only changes an already-running process's scheduling class via `sudo`'s
privilege, it never re-execs or changes that process's own UID. This
matters beyond file ownership — it's required for correctness when
`USE_DDS_SHM=true` (see below): a RouDi shared-memory daemon started by the
invoking user rejects registration from a root-owned client (`iceoryx`'s
Unix-domain registration socket creation fails across that UID boundary),
which otherwise surfaces as a fatal `Timeout registering at RouDi. Is RouDi
running?` and aborts the process.

For apples-to-apples benchmarking, lock every core's governor and min/max
frequency (and, as a stronger hardware-level backstop, the HWP MSR
request) before measuring:

```bash
sudo ./limit_ptl_cores.sh
```

This requires root and prints a per-core summary of the governor/min/max
frequency actually applied. Its targets (`FREQ_P_CORES`/`FREQ_E_CORES`/
`FREQ_LPE_CORES`, `FREQ_*_MAX`/`FREQ_*_MIN`, `CPU_MODE_P`/`CPU_MODE_E`) are
also in `env.sh`.

### Optional: production-equivalent CycloneDDS + iceoryx shared-memory setup

[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/env.sh) already defaults `RMW_IMPLEMENTATION` to
`rmw_cyclonedds_cpp` and `ROS_DOMAIN_ID` to `199`, but that alone is still
plain CycloneDDS with no iceoryx zero-copy shared-memory transport for
same-host pub/sub. [scripts/setup_dds_shm.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/setup_dds_shm.sh) adds
that missing piece — the same DDS transport Bing's own benchmark harness for
this project (`run_live_benchmark.sh`) uses on PTL/Orin, for two reasons: (1)
`rmw_fastrtps_cpp`/plain-CycloneDDS + SHM has hit CDR deserialize failures on
large `PointCloud2` bag replay — silently corrupting or dropping frames — and
(2) a dedicated DDS domain plus this transport keeps traffic isolated and
fast on a single host.

```bash
./setup_dds_shm.sh start    # installs cyclonedds/iceoryx apt packages, writes
                             # generated/cyclonedds_shm.xml + roudi_config.toml,
                             # starts the iox-roudi shared-memory daemon
./run_nclt.sh                # picks up CYCLONEDDS_URI automatically once iox-roudi is running
./setup_dds_shm.sh stop     # stop iox-roudi when done
./setup_dds_shm.sh status   # check whether iox-roudi is currently running
```

This is on by default (`USE_DDS_SHM=true` in `env.sh`) — `reproduce_all.sh`
runs `./setup_dds_shm.sh start` as one of its steps, and every colleague or
customer is free to opt out entirely (plain CycloneDDS, no SHM, no
`iox-roudi` dependency at all):

```bash
USE_DDS_SHM=false ./reproduce_all.sh
# or edit scripts/env.sh: USE_DDS_SHM="false"
```

If `run_nclt.sh` is run directly (not via `reproduce_all.sh`) and
`./setup_dds_shm.sh start` was never run first, it warns and falls back to
plain CycloneDDS rather than failing the run.

## Manual reproduction (no scripts)

Everything above is what `scripts/*.sh` automate. This section spells out the
same steps by hand — for anyone who'd rather not run scripts, or who's
forking this pipeline and wants to see exactly what each step does before
changing it. Every path/value below is one of `scripts/env.sh`'s own
defaults; run these commands from inside `pipelines/fast-lio2-demo` (all
relative paths are relative to that directory, matching `env.sh`'s own
`DEMO_DIR`).

### 1. Host dependencies

```bash
sudo apt-get install -y \
  libpcl-dev libeigen3-dev \
  ros-jazzy-pcl-ros ros-jazzy-pcl-conversions ros-jazzy-common-interfaces \
  ros-jazzy-tf2 ros-jazzy-rosbag2 ros-jazzy-rosbag2-storage-default-plugins
```

`fast_lio`'s `CMakeLists.txt`/`package.xml` unconditionally depend on
`livox_ros_driver2` (see "Limitations / non-goals" below), which in turn
needs Livox-SDK2 built from source — GCC ≥13's libstdc++ stopped pulling in
`<cstdint>` transitively, so v1.3.1's headers need it force-included:

```bash
git clone --depth 1 -b v1.3.1 https://github.com/Livox-SDK/Livox-SDK2.git /tmp/livox-sdk2
cmake -S /tmp/livox-sdk2 -B /tmp/livox-sdk2/build -DCMAKE_CXX_FLAGS="-include cstdint"
cmake --build /tmp/livox-sdk2/build -j"$(nproc)"
sudo cmake --install /tmp/livox-sdk2/build
```

### 2. Apply the Intel patches

```bash
cd FAST_LIO
git am --keep-cr ../patches/0001-Add-profiling-instrumentation-new-LiDAR-configs-and-.patch
cd ..
```

(`git am` fails on a dirty or already-patched tree — `apply_patches.sh`'s
extra safety is only needed if you're re-running this against an edited
`.patch` file.)

### 3. Build with colcon

```bash
mkdir -p ~/fast_lio2_ws/src
ln -sfn "$(pwd)/FAST_LIO" ~/fast_lio2_ws/src/fast_lio
source /opt/ros/jazzy/setup.bash

git clone --depth 1 -b 1.2.6 https://github.com/Livox-SDK/livox_ros_driver2.git ~/fast_lio2_ws/src/livox_ros_driver2
cp ~/fast_lio2_ws/src/livox_ros_driver2/package_ROS2.xml ~/fast_lio2_ws/src/livox_ros_driver2/package.xml

cd ~/fast_lio2_ws
colcon build --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy --packages-select livox_ros_driver2
source install/setup.bash
colcon build --packages-select fast_lio   # add --cmake-args -DENABLE_PROFILING=ON for the latency CSV
cd -
```

### 4. Fetch the NCLT dataset (`nclt_4`, session `2012-01-15`)

```bash
mkdir -p datasets/nclt_4 && cd datasets/nclt_4
BASE=https://s3.us-east-2.amazonaws.com/nclt.perl.engin.umich.edu
wget "${BASE}/velodyne_data/2012-01-15_vel.tar.gz"
wget "${BASE}/sensor_data/2012-01-15_sen.tar.gz"
wget "${BASE}/ground_truth/groundtruth_2012-01-15.csv"
tar -xzf 2012-01-15_vel.tar.gz
tar -xzf 2012-01-15_sen.tar.gz
cd ../..
```

This should leave `velodyne_hits.bin` and `ms25.csv` somewhere under
`datasets/nclt_4/2012-01-15/`.

### 5. Convert NCLT's raw format into a ROS 2 bag

NCLT ships a custom binary Velodyne format + CSV IMU, not a rosbag — this is
a one-time parse:

```bash
source /opt/ros/jazzy/setup.bash
python3 scripts/convert_nclt_to_bag.py \
  --dataset-dir datasets/nclt_4 \
  --output-bag datasets/nclt_4/nclt_bag \
  --storage-id sqlite3
```

### 6. Run `fastlio_mapping` against the bag

Two terminals. **Terminal A — the algorithm:**

```bash
source /opt/ros/jazzy/setup.bash
source ~/fast_lio2_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=199

ros2 run fast_lio fastlio_mapping --ros-args \
  --params-file ~/fast_lio2_ws/install/fast_lio/share/fast_lio/config/velodyne_generic.yaml \
  -p common.lid_topic:=/velodyne_points \
  -p common.imu_topic:=/imu/data \
  -p pcd_save.pcd_save_en:=false \
  -p use_sim_time:=false
```

**Terminal B — bag playback + trajectory recording** (start once Terminal A
is up and printing):

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=199

python3 scripts/record_odometry_tum.py --topic /Odometry --out datasets/nclt_4/results/nclt_4_est_tum.txt &
ros2 bag play datasets/nclt_4/nclt_bag
```

`ros2 bag play` runs at the recorded (real-time) rate — the full `nclt_4`
sequence is ~112 minutes; there's no fast-forward. Once it exits, wait a
couple of seconds for the last odometry messages to land, then stop the
recorder (`kill %1` in Terminal B) and `fastlio_mapping` (`Ctrl-C` in Terminal
A — a clean SIGTERM, not `kill -9`, so its destructor flushes any open CSV
writer). The core-pinning/SCHED_FIFO wrapping `run_nclt.sh` applies on PTL
(taskset/chrt) is an optional performance extra, not required for a
correctness repro — see "Reference: running on Intel PTL" above if you want
that too.

**Optional — the CycloneDDS+iceoryx shared-memory transport, by hand**
(equivalent to `scripts/setup_dds_shm.sh start` — run that script instead if
you don't need to customize this):

```bash
sudo apt-get install -y \
  ros-jazzy-cyclonedds ros-jazzy-rmw-cyclonedds-cpp \
  ros-jazzy-iceoryx-posh ros-jazzy-iceoryx-hoofs ros-jazzy-iceoryx-binding-c

MY_IP=$(ip route get 1.1.1.1 | awk '/src/{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
mkdir -p scripts/generated
cat > scripts/generated/cyclonedds_shm.xml <<EOF
<CycloneDDS><Domain><General>
  <AllowMulticast>true</AllowMulticast>
</General><Discovery><Peers><Peer Address="$MY_IP"/></Peers></Discovery>
<SharedMemory>
  <Enable>true</Enable>
  <LogLevel>warn</LogLevel>
</SharedMemory>
</Domain></CycloneDDS>
EOF
```

`AllowMulticast` must be `true`, not `false` — `false` plus a unicast `Peer`
pointing at your own IP reliably breaks same-host node discovery on some
machines (confirmed on Orin).

```bash
cat > scripts/generated/roudi_config.toml <<'EOF'
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
count = 20
EOF

source /opt/ros/jazzy/setup.bash
iox-roudi -c scripts/generated/roudi_config.toml --monitoring-mode off &
sleep 2
pgrep -x iox-roudi && echo "RouDi is up"
```

The mempool sizes above are sized for full `PointCloud2` scans — RouDi's own
stock example config is too small and silently drops SHM segments instead of
erroring. `--monitoring-mode off` is required: RouDi's default liveness
monitor evicts any participant that misses a ~1.5s heartbeat, which
CPU-isolation/governor/SCHED_FIFO changes can trigger even on a healthy
process.

Then, in **every** shell that needs to see the algorithm node (Terminal A,
Terminal B, and any `rviz2`/`ros2 node list` shell), export one more variable
before sourcing the ROS setup files:

```bash
export CYCLONEDDS_URI="file://$(pwd)/scripts/generated/cyclonedds_shm.xml"
```

Verify with `ros2 node list` (should show `/laser_mapping` within ~1s of
launching `fastlio_mapping`). When done: stop `fastlio_mapping`/`ros2 bag
play`, then `pkill -x iox-roudi`.

### 7. Evaluate RMSE

```bash
python3 scripts/extract_nclt_gt.py \
  --csv datasets/nclt_4/groundtruth_2012-01-15.csv \
  --out datasets/nclt_4/results/nclt_4_gt_tum.txt

pip install --user --break-system-packages evo   # if not already installed
evo_ape tum datasets/nclt_4/results/nclt_4_gt_tum.txt datasets/nclt_4/results/nclt_4_est_tum.txt -a
```

Compare the printed RMSE against the documented `nclt_4` baseline of **8.6 m**
(FAST-LIO2 paper, arXiv 2107.06829, Table IV) — a fresh measurement up to 20%
above that baseline is an expected pass, since the check exists to catch
regressions rather than to require beating the paper's own number.

## Limitations / non-goals

- Validated here: functional LIO operation and pose-tracking accuracy
  (RMSE) against the public NCLT baseline, on a Velodyne-class LiDAR.
- `fast_lio`'s build unconditionally depends on `livox_ros_driver2` (and
  transitively Livox-SDK2), even though this pipeline only ever runs the
  Velodyne/NCLT path — confirmed in `CMakeLists.txt`/`package.xml`, not a
  choice made by this integration.
- The NCLT Velodyne/IMU binary-format parsing in
  [scripts/convert_nclt_to_bag.py](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/convert_nclt_to_bag.py) and the
  ground-truth parsing in
  [scripts/extract_nclt_gt.py](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-lio2-demo/scripts/extract_nclt_gt.py) were verified
  against NCLT's own devkit scripts and a real (partial) download of the
  `nclt_4` session's raw files — but a full end-to-end `reproduce_all.sh`
  run (through `fastlio_mapping` and RMSE evaluation) has not been
  exercised in the environment this was authored in, which lacks a ROS 2
  install; validate on your own machine or PTL before relying
  on the PASS/FAIL result.
- Only `nclt_4` has a confirmed session date and documented baseline;
  `nclt_5`–`nclt_10` are structural placeholders in `scripts/env.sh` for
  future extension, not yet populated.
- NCLT's terms of use should be checked on the
  [dataset's own page](http://robots.engin.umich.edu/nclt/) before
  redistributing any downloaded data.
- GPLv2 licensing (see callout above) applies to the upstream code as-is;
  this integration does not change that.
