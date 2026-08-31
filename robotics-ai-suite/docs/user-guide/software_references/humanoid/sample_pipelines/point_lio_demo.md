# LIO SLAM: Point-LIO

Point-LIO is a robust, high-bandwidth LiDAR-Inertial Odometry system built on
a point-by-point EKF update (no per-frame accumulation, so no in-frame
motion distortion) and a stochastic-process-augmented kinematic model that
tolerates IMU saturation during aggressive motion.

![Point-LIO system overview](https://github.com/hku-mars/Point-LIO/raw/master/image/toc4.png)

- Paper: [Point-LIO: Robust High-Bandwidth Light Detection and Ranging Inertial Odometry](https://doi.org/10.1002/aisy.202200459) (He, Xu, Chen, Kong, Yuan, Zhang — *Advanced Intelligent Systems*, 2023, DOI 10.1002/aisy.202200459)
- Upstream: [hku-mars/Point-LIO](https://github.com/hku-mars/Point-LIO) (`point-lio-with-grid-map` branch)

In Robotics AI Suite, the upstream tree is a pristine git submodule and Intel
changes ship as patches on top, so Point-LIO can be evaluated as an
alternative LIO backend without forking the reference navigation stack.

> [!NOTE]
> Point-LIO's [LICENSE](https://github.com/hku-mars/Point-LIO/blob/point-lio-with-grid-map/LICENSE) is **BSD-3-Clause**, and its
> `package.xml` correctly declares this. No compliance caveat is needed here.

## Changes to 3rd party source

This work is based on the open-source
[Point-LIO](https://github.com/hku-mars/Point-LIO.git) repository
(`point-lio-with-grid-map` branch), pinned in
[.gitmodules](https://github.com/open-edge-platform/edge-ai-suites/blob/main/.gitmodules) at the upstream commit the patch below
applies to.

| Patch | Change |
| ----- | ------ |
| [0001-Port-Point-LIO-to-ROS2-and-add-benchmarking-instrume.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/patches/0001-Port-Point-LIO-to-ROS2-and-add-benchmarking-instrume.patch) | Full ROS1/catkin → ROS2/ament_cmake port (rclcpp, `livox_ros_driver2`, a ROS2 launch file); new `avia_ros2.yaml`/`mid360_ros2.yaml`/`velodyne_urbanloco.yaml` configs — the last one is the UrbanLoco `ulhk_4` config used for validation below; opt-in latency-profiling CSV (below); `MP_PROC_NUM_CPUSET` CMake option to pin OpenMP thread count to the algorithm's cpuset; a segfault fix for point clouds without a `time` field; and alignment of Avia point filtering with FAST-LIO2 for fair benchmarking. |
| [0002-Reformat-sources-to-match-the-project-s-real-clang-f.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/patches/0002-Reformat-sources-to-match-the-project-s-real-clang-f.patch) | Reformats `laserMapping.cpp` and `preprocess.cpp` to the Google-based clang-format style used elsewhere in this fork; no logic changes. |
| [0003-Fix-early-loop-exit-and-a-distance-threshold-typo.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/patches/0003-Fix-early-loop-exit-and-a-distance-threshold-typo.patch) | Drops a stray `break` in the first-frame IMU-init block (both `kf_input`/`kf_output` paths) that silently skipped queued IMU messages; fixes a `disA`/`disB` typo in `Preprocess`'s constructor; guards `plane_judge` against a zero-area divide and an out-of-bounds distance-array read; checks `mkdir()`'s return value; wraps `main()` in a try/catch. |

**Profiling**: built behind the `ENABLE_PROFILING` CMake option (off by
default, matching upstream). When enabled, a lock-free ring buffer plus a
dedicated writer thread records per-stage timing (using `CLOCK_MONOTONIC`,
immune to PTP clock steps) to `Point-LIO/Log/point_lio_profiling.csv`.

## Environment setup (Ubuntu 24.04 / ROS 2 Jazzy)

```bash
# 1. Fetch the pristine upstream submodule (no --recursive needed - this
# Point-LIO branch has no nested submodule)
git submodule update --init robotics-ai-suite/pipelines/point-lio-demo/Point-LIO

cd robotics-ai-suite/pipelines/point-lio-demo/scripts

# 2. One-time host dependencies (needs sudo; safe to re-run)
./install_deps.sh

# 3. Apply the Intel patches from the table above
./apply_patches.sh

# 4. Build point_lio with colcon
./build.sh
```

All paths, the ROS distro, and the dataset sequence used below are
centralized in [scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/scripts/env.sh) — edit that one file to
retarget a different workspace/sequence; nothing else needs to change.

## Validate without hardware: UrbanLoco dataset replay

No robot or sensor is required to verify the build and measure accuracy: the
`ulhk_4` sequence (`HK-Data20190117`) from the public
[UrbanLoco dataset](https://github.com/weisongwen/UrbanLoco) (PolyU IPN-Lab,
ICRA 2020; official site
[advdataset2019.wixsite.com/urbanloco](https://advdataset2019.wixsite.com/urbanloco/hong-kong))
is replayed through `pointlio_mapping` and compared against its NovAtel
SPAN-CPT-derived ground truth.

```bash
./fetch_ulhk.sh            # checks whether the file is already there; otherwise prints download links + target path
./convert_ulhk_to_bag.sh   # one-time conversion into a standard ROS 2 bag, if needed
./run_ulhk.sh              # launch pointlio_mapping + `ros2 bag play` the converted bag, records the trajectory
./evaluate_rmse.sh         # evo_ape RMSE vs. ground truth, printed next to the documented baseline

# or, once install_deps.sh has been run once and the file has been downloaded by hand:
./reproduce_all.sh # apply patch -> build -> check dataset -> convert -> run -> evaluate, in one command
```

UrbanLoco has no scriptable download: its listed Google Drive links require
a manual "can't scan for viruses" confirmation step and, in practice, are
often unreachable at all from a corporate network even with an account.
`fetch_ulhk.sh` does **not** attempt an automated download — it only checks
whether the file is already present, and otherwise prints the Dropbox and
Baidu Netdisk links from the dataset's own GitHub README (same shared
folder for every Hong Kong sequence) plus the exact path to place the file
at; re-run `./fetch_ulhk.sh` afterward (it detects the file is already
present) or continue straight to `./convert_ulhk_to_bag.sh`.

During replay, `pointlio_mapping`'s own log will repeat
`Failed to find match for field 'time'.` once per LiDAR scan for the whole
run — this is **expected and harmless**, not a sign of a broken pipeline.
It's a PCL-level warning (see `Point-LIO/README.md`'s note C) that the
incoming `PointCloud2` has no per-point timestamp field; UrbanLoco's 2019
Velodyne recording predates that convention, so Point-LIO falls back to
estimating each point's capture time from scan geometry instead (still
correct, just an internal fallback path). This is specific to this public
dataset's age — a real Velodyne (or other) LiDAR driver on live hardware
does populate that field, so production/live-sensor runs of this pipeline
won't print this at all.

For `ulhk_4`, the documented baseline is **2.17 m** RMSE (Point-LIO paper,
DOI 10.1002/aisy.202200459, Table 5). FAST-LIO2's own paper (Xu et al. 2022,
IEEE T-RO, Table IV) reports 2.57 m on the same sequence, printed alongside
for context only, not compared against. The check is one-sided: it passes
as long as the freshly measured RMSE does not exceed the Point-LIO baseline
by more than `RMSE_TOLERANCE_PCT` (20% by default) — a measured RMSE *lower*
than the baseline always passes, since the check exists to catch
regressions, not to flag outperforming the paper's own number.

### Rviz visualization

`run_ulhk.sh` gates `rviz2` behind the `USE_RVIZ` variable in
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/scripts/env.sh), off by default so the flow stays headless
over SSH:

```bash
USE_RVIZ=true ./run_ulhk.sh   # or: USE_RVIZ=true ./reproduce_all.sh
```

Run this directly on the target machine's own logged-in Ubuntu desktop
session (e.g. on the PTL board's display, not over plain SSH) — rviz2's
point-cloud rendering needs a real GPU display, so X11-forwarding it over
SSH is impractical.

### Reference: running on Intel PTL

`run_ulhk.sh` ships a reference core-pinning + frequency-locking setup for
Intel PTL (validated on Core Ultra X7 358H: 4 P-cores `cpu0-3` up to 4700
MHz, 8 E-cores `cpu4-11` up to 3500 MHz, 4 LP-E-cores `cpu12-15` up to 3300
MHz). Core numbering is specific to this SKU — re-check `lscpu -e` before
reusing these defaults on a different PTL SKU or platform.

| Task | Pinned to | Why |
| ---- | --------- | --- |
| `pointlio_mapping` algorithm | LP-E cores `12,13` (`CPUSET_ALGO`) | Keeps the timing-critical LIO thread on isolated cores the general scheduler and rest of the OS don't touch. |
| `ros2 bag play` of the converted UrbanLoco bag | P-core `1` (`CPUSET_BAG`) | Replaying the pre-converted bag is bursty I/O + decode work; a dedicated P-core keeps it from stealing cycles from the algorithm cores. |
| `rviz2` (when `USE_RVIZ=true`) | P-core `2` (`CPUSET_RVIZ`) | Point-cloud rendering is bursty GUI work best kept off the algorithm's isolated cores; a P-core has the headroom for it. |

`run_ulhk.sh` wraps the algorithm and `ros2 bag play` with `taskset -c` and,
best-effort, `sudo -n chrt -f -a -p 85 <pid>` SCHED_FIFO priority-85 —
applied to the process *after* it's already launched as the invoking
(non-root) user, not chained into the launch itself, so it inherits this
script's own exported environment (`ROS_DOMAIN_ID`/`RMW_IMPLEMENTATION`/
`CYCLONEDDS_URI`) unchanged — whenever the matching `CPUSET_*` variable in
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/scripts/env.sh) is non-empty (the default). Since `ros2
run` (used to launch the algorithm) `subprocess.Popen()`s the actual
`pointlio_mapping` binary as a separate child rather than exec()'ing into
it, `chrt` is applied to that whole process tree, not just the top PID —
otherwise only the idle Python wrapper gets SCHED_FIFO and the real
workload runs unprioritized (confirmed 2026-08-03: this let
`pointlio_mapping` fall behind real-time on the LP-E cores during a
full-length `ulhk_4` run and exhaust the iceoryx SHM mempool). `rviz2` gets
`taskset` pinning only, no realtime priority. If `sudo -n` isn't usable (no
passwordless sudoers entry for `chrt`), the script warns and continues
unprioritized rather than failing the run. To disable pinning for a given
task, blank out its variable in `env.sh` (e.g. `CPUSET_ALGO=""`).

Every process `run_ulhk.sh` launches — including the RT-prioritized ones —
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

[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/scripts/env.sh) already defaults `RMW_IMPLEMENTATION` to
`rmw_cyclonedds_cpp` and `ROS_DOMAIN_ID` to `200`, but that alone is still
plain CycloneDDS with no iceoryx zero-copy shared-memory transport for
same-host pub/sub. [scripts/setup_dds_shm.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/point-lio-demo/scripts/setup_dds_shm.sh) adds
that missing piece — the same DDS transport Bing's own benchmark harness for
this project (`run_live_benchmark.sh`) uses on PTL/Orin, for two reasons:
(1) `rmw_fastrtps_cpp`/plain-CycloneDDS + SHM has hit CDR deserialize
failures on large `PointCloud2` bag replay — silently corrupting or dropping
frames — and (2) a dedicated DDS domain plus this transport keeps traffic
isolated and fast on a single host.

```bash
./setup_dds_shm.sh start   # installs cyclonedds/iceoryx apt packages, writes
                            # generated/cyclonedds_shm.xml + roudi_config.toml,
                            # stops any already-running iox-roudi (even an
                            # orphaned one from a previous session) and
                            # starts a fresh one with this config
./run_ulhk.sh               # picks up CYCLONEDDS_URI automatically once iox-roudi is running
./setup_dds_shm.sh stop    # stop iox-roudi when done
./setup_dds_shm.sh status  # check whether iox-roudi is currently running
```

This is on by default (`USE_DDS_SHM=true` in `env.sh`) — `reproduce_all.sh`
runs `./setup_dds_shm.sh start` as one of its steps, and every colleague or
customer is free to opt out entirely (plain CycloneDDS, no SHM, no
`iox-roudi` dependency at all):

```bash
USE_DDS_SHM=false ./reproduce_all.sh
# or edit scripts/env.sh: USE_DDS_SHM="false"
```

If `run_ulhk.sh` is run directly (not via `reproduce_all.sh`) and
`./setup_dds_shm.sh start` was never run first, it warns and falls back to
plain CycloneDDS rather than failing the run.

## Manual reproduction (no scripts)

Everything above is what `scripts/*.sh` automate. This section spells out
the same steps by hand — for anyone who'd rather not run scripts, or who's
forking this pipeline and wants to see exactly what each step does before
changing it. Every path/value below is one of `scripts/env.sh`'s own
defaults; run these commands from inside `pipelines/point-lio-demo` (all
relative paths are relative to that directory, matching `env.sh`'s own
`DEMO_DIR`).

### 1. Host dependencies

```bash
sudo apt-get install -y \
  libpcl-dev libeigen3-dev \
  ros-jazzy-pcl-conversions ros-jazzy-common-interfaces \
  ros-jazzy-tf2 ros-jazzy-tf2-ros ros-jazzy-tf2-geometry-msgs \
  ros-jazzy-rosbag2 ros-jazzy-rosbag2-storage-default-plugins
pip install --user --break-system-packages rosbags evo
```

`point_lio`'s `CMakeLists.txt`/`package.xml` unconditionally depend on
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
cd Point-LIO
git am --keep-cr ../patches/0001-Port-Point-LIO-to-ROS2-and-add-benchmarking-instrume.patch
git am --keep-cr ../patches/0002-Reformat-sources-to-match-the-project-s-real-clang-f.patch
git am --keep-cr ../patches/0003-Fix-early-loop-exit-and-a-distance-threshold-typo.patch
cd ..
```

(`git am` fails on a dirty or already-patched tree — `apply_patches.sh`'s
extra safety is only needed if you're re-running this against an edited
`.patch` file.)

### 3. Build with colcon

```bash
mkdir -p ~/point_lio_ws/src
ln -sfn "$(pwd)/Point-LIO" ~/point_lio_ws/src/point_lio
source /opt/ros/jazzy/setup.bash

git clone --depth 1 -b 1.2.6 https://github.com/Livox-SDK/livox_ros_driver2.git ~/point_lio_ws/src/livox_ros_driver2
cp ~/point_lio_ws/src/livox_ros_driver2/package_ROS2.xml ~/point_lio_ws/src/livox_ros_driver2/package.xml

cd ~/point_lio_ws
colcon build --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy --packages-select livox_ros_driver2
source install/setup.bash
colcon build --packages-select point_lio   # add --cmake-args -DENABLE_PROFILING=ON for the latency CSV
cd -
```

### 4. Fetch the UrbanLoco dataset (`ulhk_4`, session `HK-Data20190117`) — manual download

UrbanLoco has no scriptable download. Download the `HK-Data20190117` entry
from section "2. Hong Kong Dataset" of the
[UrbanLoco GitHub README](https://github.com/weisongwen/UrbanLoco) via
either mirror it lists (Google Drive is frequently unreachable from
corporate networks even with an account, so these are the reliable ones):

- Dropbox: <https://www.dropbox.com/scl/fo/zrsmoddbq96t4go1wbxwp/AJw_DGVXng06DmLx9j9iQMs?rlkey=rk11n8tt62ejbg8mbixrm6quz&e=1&st=j7sy3izj&dl=0>
- Baidu Netdisk (百度网盘): <https://pan.baidu.com/s/1-5d8xM1tzfsSSueTiU6-MQ?pwd=sufc>

(same shared folder for every Hong Kong sequence — open the
`HK-Data20190117` entry inside it). Place the downloaded ROS1 bag at:

```bash
mkdir -p datasets/ulhk_4
mv ~/Downloads/HK-Data20190117.bag datasets/ulhk_4/HK-Data20190117.bag
```

### 5. Convert to a ROS 2 bag

UrbanLoco's public download is a ROS1 bag:

```bash
source /opt/ros/jazzy/setup.bash
rosbags-convert --src datasets/ulhk_4/HK-Data20190117.bag --dst datasets/ulhk_4/ulhk_bag
```

### 6. Run `pointlio_mapping` against the bag

Two terminals. **Terminal A — the algorithm:**

```bash
source /opt/ros/jazzy/setup.bash
source ~/point_lio_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=200

ros2 run point_lio pointlio_mapping --ros-args \
  --params-file ~/point_lio_ws/install/point_lio/share/point_lio/config/velodyne_urbanloco.yaml
```

**Terminal B — bag playback + trajectory recording** (start once Terminal A
is up and printing):

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=200

python3 scripts/record_odometry_tum.py --topic /aft_mapped_to_init --out datasets/ulhk_4/results/ulhk_4_est_tum.txt &
ros2 bag play datasets/ulhk_4/ulhk_bag
```

`ros2 bag play` runs at the recorded (real-time) rate — `ulhk_4` is ~5:18.
Once it exits, wait a couple of seconds for the last odometry messages to
land, then stop the recorder (`kill %1` in Terminal B) and
`pointlio_mapping` (`Ctrl-C` in Terminal A — a clean SIGTERM, not `kill -9`,
so its destructor flushes any open CSV writer). The core-pinning/SCHED_FIFO
wrapping `run_ulhk.sh` applies on PTL (taskset/chrt) is an optional
performance extra, not required for a correctness repro — see "Reference:
running on Intel PTL" above if you want that too.

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
count = 100
EOF

pkill -x iox-roudi 2>/dev/null; sleep 1   # replace any already-running instance, don't run two
source /opt/ros/jazzy/setup.bash
iox-roudi -c scripts/generated/roudi_config.toml --monitoring-mode off &
sleep 2
pgrep -x iox-roudi && echo "RouDi is up"
```

The mempool sizes above are sized for full `PointCloud2` scans — RouDi's own
stock example config is too small and silently drops SHM segments instead of
erroring. The largest pool's `count` is 100, not RouDi's smaller stock
value, after a full-length `ulhk_4` run (~10Hz scans over 5:21) hit
`MemoryManager: unable to acquire a chunk`/
`MEPOO__MEMPOOL_GETCHUNK_POOL_IS_RUNNING_OUT_OF_CHUNKS` — see `scripts/
run_ulhk.sh`'s `ptl_wrap` comment for the actual root cause (real-time
priority wasn't reaching `pointlio_mapping`'s actual process), this pool
bump is just extra headroom on top of that fix. `--monitoring-mode off` is
required: RouDi's default liveness monitor evicts any participant that
misses a ~1.5s heartbeat, which CPU-isolation/governor/SCHED_FIFO changes
can trigger even on a healthy process. Always stop any already-running
`iox-roudi` before starting a new one (as above) — an old instance left
over from a previous session will keep running with its own (possibly
stale) config instead of erroring, since a second RouDi wouldn't overwrite
it.

Then, in **every** shell that needs to see the algorithm node (Terminal A,
Terminal B, and any `rviz2`/`ros2 node list` shell), export one more variable
before sourcing the ROS setup files:

```bash
export CYCLONEDDS_URI="file://$(pwd)/scripts/generated/cyclonedds_shm.xml"
```

Verify with `ros2 node list` (should show `/pointlio_mapping` within ~1s of
launching it). When done: stop `pointlio_mapping`/`ros2 bag play`, then
`pkill -x iox-roudi`.

### 7. Evaluate RMSE

```bash
python3 scripts/extract_ulhk_gt.py \
  --bag-dir datasets/ulhk_4/ulhk_bag \
  --topic /novatel_data/inspvax \
  --out datasets/ulhk_4/results/ulhk_4_gt_tum.txt

pip install --user --break-system-packages evo   # if not already installed
evo_ape tum datasets/ulhk_4/results/ulhk_4_gt_tum.txt datasets/ulhk_4/results/ulhk_4_est_tum.txt -a
```

Compare the printed RMSE against the documented `ulhk_4` baseline of
**2.17 m** (Point-LIO paper, DOI 10.1002/aisy.202200459, Table 5) — a fresh
measurement up to 20% above that baseline is an expected pass, since the
check exists to catch regressions rather than to require beating the
paper's own number.

## Limitations / non-goals

- **Validated end-to-end on Intel PTL** (Core Ultra X7 358H): a full
  `reproduce_all.sh`-equivalent run (patch → build → run → evaluate)
  produced a measured RMSE of **1.859 m** on `ulhk_4`, comfortably passing
  the ≤2.604 m (baseline × 1.20) gate against the documented 2.17 m
  Point-LIO baseline.
- Validated here: functional LIO operation and pose-tracking accuracy
  (RMSE) against the public UrbanLoco baseline, on a Velodyne HDL-32E LiDAR.
- `point_lio`'s build unconditionally depends on `livox_ros_driver2` (and
  transitively Livox-SDK2), even though this pipeline only ever runs the
  Velodyne/UrbanLoco path — confirmed in `CMakeLists.txt`/`package.xml`, not
  a choice made by this integration.
- Ground truth (`scripts/extract_ulhk_gt.py`) reads NovAtel SPAN-CPT
  INSPVAX messages directly out of the converted bag's `.db3` file by fixed
  CDR byte offset, rather than deserializing through the
  `novatel_oem7_msgs` package definitions — this avoids an extra ROS
  package dependency just to read ground truth, but is specific to the CDR
  layout of that message type as recorded in this dataset; re-verify the
  byte offsets (`_OFF_LAT`/`_OFF_LON`/`_OFF_HGT` in that script) if adapting
  this to a different bag.
- Only `ulhk_4` has a confirmed session name and documented baseline;
  `ulhk_5`/`ulhk_6` are structural placeholders in `scripts/env.sh` for
  future extension, not yet populated.
- The converted `ulhk_4` bag's `PointCloud2` has no per-point `time` field
  (see "Validate without hardware" above for why `pointlio_mapping` logs
  "Failed to find match for field 'time'" once per scan because of this).
  This is non-fatal — Point-LIO falls back to a scan-rate-based per-point
  time estimate — and the 1.859 m measured RMSE already reflects this; it
  is not a config bug to fix.
- `ros2 bag play` skips republishing `ublox_msgs`/`novatel_oem7_msgs`-typed
  topics (including the ground-truth `/novatel_data/inspvax`) since those
  packages aren't installed by `install_deps.sh` — expected and harmless,
  since `extract_ulhk_gt.py` reads ground truth directly from the bag's own
  `.db3` file rather than subscribing to a live topic.
- UrbanLoco has no scriptable download (see "Validate without hardware"
  above) — Google Drive's automated-download detection gates this specific
  shared file behind a sign-in wall that plain `wget`/`curl` (or an
  unattended script) can't get past, confirmed unreachable in practice even
  with an account, from more than one network. `fetch_ulhk.sh` only checks
  for the file and prints the Dropbox/Baidu Netdisk links to download it by
  hand instead.
- UrbanLoco's terms of use should be checked on the
  [dataset's own page](https://advdataset2019.wixsite.com/urbanloco/hong-kong)
  before redistributing any downloaded data.
- BSD-3-Clause licensing (see callout above) applies to the upstream code
  as-is; this integration does not change that.