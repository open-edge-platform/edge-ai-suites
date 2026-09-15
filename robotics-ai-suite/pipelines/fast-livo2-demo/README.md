# LIVO SLAM: FAST-LIVO2

FAST-LIVO2 is a direct (feature-less) LiDAR-Inertial-Visual Odometry system:
it fuses a LiDAR-Inertial pose estimate with dense visual-inertial tracking on
raw image patches, avoiding explicit feature extraction/matching. It targets
real-time onboard localization and mapping, including in visually- or
geometrically-degraded environments where either sensor alone struggles.

<div align="center">
    <img src="https://raw.githubusercontent.com/hku-mars/FAST-LIVO2/0d2c0346107b75b59934975adec9a6eeeb913c64/pics/Framework.png" width="80%">
</div>

- Paper: [FAST-LIVO2: Fast, Direct LiDAR-Inertial-Visual Odometry](https://arxiv.org/pdf/2408.14035) (accepted, T-RO'24)
- Paper: [FAST-LIVO2 on Resource-Constrained Platforms](https://arxiv.org/pdf/2501.13876)
- Upstream: [hku-mars/FAST-LIVO2](https://github.com/hku-mars/FAST-LIVO2)

In Robotics AI Suite, the upstream tree is a pristine git submodule and Intel
changes ship as patches on top, so FAST-LIVO2 can be evaluated as an
alternative SLAM backend without forking the reference navigation stack.

> [!IMPORTANT]
> FAST-LIVO2 is released under **GPLv2**. For commercial use, contact the
> upstream authors (see [FAST-LIVO2/README.md](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/README.md#5-license))
> for an alternative license before shipping it in a product.

## Changes to 3rd party source

This work is based on the open-source
[FAST-LIVO2](https://github.com/hku-mars/FAST-LIVO2.git) repository, pinned in
[.gitmodules](https://github.com/open-edge-platform/edge-ai-suites/blob/main/.gitmodules) at the upstream commit the patches below
apply to.

| Patch | Enhancement |
| ----- | ----------- |
| [0001-Stop-VIO-waiting-on-the-LiDAR-buffer-in-LIVO-mode.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/patches/0001-Stop-VIO-waiting-on-the-LiDAR-buffer-in-LIVO-mode.patch) | Removes a LiDAR-buffer precondition that gated every VIO update even though the VIO step never reads the LiDAR queue. Measured: ~30 ms of gate wait removed per VIO update at 10 Hz LiDAR input ([src/LIVMapper.cpp](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/src/LIVMapper.cpp)). |
| [0002-Port-to-ROS2-and-bring-up-Mid-360-D415-on-A2W.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/patches/0002-Port-to-ROS2-and-bring-up-Mid-360-D415-on-A2W.patch) | Ports the codebase and launch files from ROS1/catkin to ROS2/ament (validated on Humble and Jazzy, see [FAST-LIVO2/README_ROS2.md](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/README_ROS2.md)); adds a Livox Mid-360 + RealSense D415 sensor profile; adds an optional per-frame LIO/VIO timing CSV export gated behind `-DENABLE_PERFRAME_TIMING=ON` (off by default) for latency analysis; fixes a DDS parameter-discovery race and an inverted Mid-360 mount orientation. |
| [0003-Size-OMP-thread-count-from-runtime-CPU-affinity.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/patches/0003-Size-OMP-thread-count-from-runtime-CPU-affinity.patch) | Sizes the LIO/VIO OMP thread count from the process's actual CPU affinity at startup (`sched_getaffinity`) instead of the build-time total host core count, so pinning `fast_livo2` to a smaller cpu set via `taskset -c` (`CPUSET_ALGO` in `scripts/env.sh`) no longer oversubscribes the pinned cores with more OMP threads than they can run. Falls back to the original `ProcessorCount`-based build-time default when the process isn't affinity-restricted. |
| [0004-Reformat-sources-to-the-real-clang-format-style.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/patches/0004-Reformat-sources-to-the-real-clang-format-style.patch) | Reformats `IMU_Processing.cpp`, `LIVMapper.cpp`, `main.cpp`, `preprocess.cpp`, and `vio.cpp` to the Google-based clang-format style used elsewhere in this fork; no logic changes. |
| [0005-Fix-crash-race-risks-and-an-info-leak-in-the-ROS2-no.patch](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/patches/0005-Fix-crash-race-risks-and-an-info-leak-in-the-ROS2-no.patch) | Wraps `main()` in a try/catch so a startup exception logs via `RCLCPP_FATAL` instead of taking the node down unhandled; reorders null-pointer checks to test-before-dereference and repositions two mutex locks so the shared state they guard is actually covered; guards three VIO score/residual computations and `plane_judge` against division by zero; frees a leaked scratch patch buffer in `updateVisualMapPoints`; replaces an internal lab IP address in a camera-intrinsics config comment with a generic rig description (a BDBA information-leakage finding); lists the ROS2-port maintainer in `package.xml`. |

## Environment setup (Ubuntu 24.04 / ROS 2 Jazzy, Intel Core Ultra / PTL)

Full one-time host prerequisites (system packages, Livox-SDK2, Sophus,
vikit_common) are documented once in
[FAST-LIVO2/README_ROS2.md](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/README_ROS2.md) — the steps below just
automate exactly those commands via [scripts](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts):

```bash
# 1. Fetch the pristine upstream submodule
git submodule update --init robotics-ai-suite/pipelines/fast-livo2-demo/FAST-LIVO2

cd robotics-ai-suite/pipelines/fast-livo2-demo/scripts

# 2. One-time host dependencies (needs sudo; safe to re-run)
./install_deps.sh

# 3. Apply the Intel patches from the table above
./apply_patches.sh

# 4. Build fast_livo2 with colcon
./build.sh
```

All paths, the ROS distro, and the dataset sequence used below are
centralized in [scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh) — edit that one file to
retarget a different workspace/sequence; nothing else needs to change.

## Validate without hardware: NTU VIRAL dataset replay

No robot or sensor is required to verify the build and measure accuracy: the
Ouster OS1 + camera + IMU `eee_01` sequence from the public
[NTU VIRAL dataset](https://ntu-aris.github.io/ntu_viral_dataset/)
(Nguyen et al., *NTU VIRAL: A Visual-Inertial-Ranging-Lidar Dataset, From an
Aerial Vehicle Viewpoint*, IJRR 2022) is replayed through the same
`fast_livo2` binary and compared against surveyed ground truth.

```bash
./fetch_ntu_viral.sh          # download eee_01 bag + convert to ROS2 (auto; manual fallback for unlisted sequences)
./run_ntu_viral.sh            # launch fast_livo2 + play back the bag, records the trajectory
./evaluate_rmse.sh            # evo_ape RMSE vs. ground truth, printed next to the documented baseline

# or, once install_deps.sh has been run once:
./reproduce_all.sh            # apply patches -> build -> fetch -> run -> evaluate, in one command
```

`evaluate_rmse.sh` reproduces the same PRISM-frame conversion and `evo_ape`
comparison already checked into
[FAST-LIVO2/Log/result/ntu_viral/](https://github.com/hku-mars/FAST-LIVO2/tree/0d2c0346107b75b59934975adec9a6eeeb913c64/Log/result/ntu_viral), whose
`README.md` documents reference RMSE for all nine sequences from prior runs.
For `eee_01`, the documented baseline is **2.71 cm**; the script passes when
the freshly measured RMSE does not exceed that baseline by more than
`RMSE_TOLERANCE_PCT` (20% by default, see
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh)) — not a specific
improvement claim.

### Rviz visualization

`run_ntu_viral.sh` gates `rviz2` behind the `USE_RVIZ` variable in
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh), off by default so the flow stays headless
over SSH:

```bash
USE_RVIZ=true ./run_ntu_viral.sh   # or: USE_RVIZ=true ./reproduce_all.sh
```

Run this directly on the target machine's own logged-in Ubuntu desktop
session (e.g. on the PTL board's display, not over plain SSH) — rviz2's
point-cloud rendering needs a real GPU display, so X11-forwarding it over
SSH is impractical. It opens with the
[ntu_viral.rviz](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/rviz_cfg/ntu_viral.rviz) config, showing the
live point cloud and pose trajectory as the bag plays back.

### Reference: running on Intel PTL

`run_ntu_viral.sh` ships a reference core-pinning + frequency-locking
setup for Intel PTL (validated on Core Ultra X7 358H: 4 P-cores `cpu0-3` up
to 4700 MHz, 8 E-cores `cpu4-11` up to 3500 MHz, 4 LP-E-cores `cpu12-15` up
to 3300 MHz). Core numbering is specific to this SKU — re-check `lscpu -e`
before reusing these defaults on a different PTL SKU or platform.

| Task | Pinned to | Why |
| ---- | --------- | --- |
| `fast_livo2` algorithm | LP-E cores `12,13` (`CPUSET_ALGO`) | Keeps the timing-critical LIO/VIO threads on isolated cores the general scheduler and rest of the OS don't touch. |
| `ros2 bag play` | P-core `1` (`CPUSET_BAG`) | Bag replay is bursty I/O + deserialization work; a dedicated P-core keeps it from stealing cycles from the algorithm cores. |
| `rviz2` (when `USE_RVIZ=true`) | P-core `2` (`CPUSET_RVIZ`) | Point-cloud rendering is bursty GUI work best kept off the algorithm's isolated cores; a P-core has the headroom for it. |

These three assignments are independent of each other and of `USE_RVIZ`:
the algorithm always runs on `12,13` whether or not rviz is enabled, and
`rviz2` always runs as its own separate process on P-core `2` (never as a
child of the algorithm's `ros2 launch`, so it never shares or inherits the
algorithm's affinity).

This assumes `cpu12,13` (the isolated core set used for real-time work)
have already been isolated from the general kernel scheduler at the
platform/BKC level (e.g. `isolcpus=`/equivalent boot config) — that
isolation is out of scope for this repo and expected to already be in
place on the target machine.

`run_ntu_viral.sh` automatically wraps the `fast_livo2` launch and
`ros2 bag play` with `taskset -c` and, best-effort,
`sudo -n chrt -f -a -p 85 <pid>` SCHED_FIFO priority-85 — applied to the
process *after* it's already launched as the invoking (non-root) user, not
chained into the launch itself — whenever the matching `CPUSET_*` variable
in [scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh) is non-empty (the default). `rviz2`
gets `taskset` pinning only, no realtime priority — GUI rendering work
shouldn't run SCHED_FIFO. If `sudo -n` isn't usable (no passwordless
sudoers entry for `chrt`), the script warns and continues unprioritized
rather than failing the run. To disable pinning for a given task, blank
out its variable in `env.sh` (e.g. `CPUSET_ALGO=""`).

`fast_livo2` sizes its LIO/VIO OMP thread count from its actual runtime CPU
affinity (detected via `sched_getaffinity` at startup, see patch 0003 above),
not a value baked in at build time — so changing `CPUSET_ALGO` takes effect
on the next run, no rebuild needed. Running unpinned (`CPUSET_ALGO=""`) falls
back to the original build-time `ProcessorCount`-based default.

Every process `run_ntu_viral.sh` launches — including the RT-prioritized
ones — stays owned by the invoking user throughout, never root: `chrt -p
<pid>` only changes an already-running process's scheduling class via
`sudo`'s privilege, it never re-execs or changes that process's own UID.
This matters beyond file ownership — it's required for correctness when
`USE_DDS_SHM=true` (see below): a RouDi shared-memory daemon started by the
invoking user rejects registration from a root-owned client (`iceoryx`'s
Unix-domain registration socket creation fails across that UID boundary),
which otherwise surfaces as a fatal `Timeout registering at RouDi. Is
RouDi running?` and aborts the process.

For apples-to-apples benchmarking, lock every core's governor and
min/max frequency (and, as a stronger hardware-level backstop, the HWP
MSR request) before measuring:

```bash
sudo ./limit_ptl_cores.sh
```

This requires root (it writes to `/sys/devices/system/cpu/*/cpufreq` and,
if `msr-tools` is installed, MSR `0x774`) and prints a per-core summary of
the governor/min/max/current frequency actually applied. Its targets
(`FREQ_P_CORES`/`FREQ_E_CORES`/`FREQ_LPE_CORES`, `FREQ_*_MAX`/`FREQ_*_MIN`,
`CPU_MODE_P`/`CPU_MODE_E`) are also in `env.sh`.

### Optional: production-equivalent CycloneDDS + iceoryx shared-memory setup

[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh) already defaults `RMW_IMPLEMENTATION` to
`rmw_cyclonedds_cpp` and `ROS_DOMAIN_ID` to `199`, but that alone is still
plain CycloneDDS with no iceoryx zero-copy shared-memory transport for
same-host pub/sub. [scripts/setup_dds_shm.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/setup_dds_shm.sh) adds
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
./run_ntu_viral.sh          # picks up CYCLONEDDS_URI automatically once iox-roudi is running
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

If `run_ntu_viral.sh` is run directly (not via `reproduce_all.sh`) and
`./setup_dds_shm.sh start` was never run first, it warns and falls back to
plain CycloneDDS rather than failing the run.

## Manual reproduction (no scripts)

Everything above is what `scripts/*.sh` automate. This section spells out the
same steps by hand — for anyone who'd rather not run scripts, or who's
forking this pipeline and wants to see exactly what each step does before
changing it. Every path/value below is one of `scripts/env.sh`'s own
defaults; run these commands from inside `pipelines/fast-livo2-demo` (all
relative paths are relative to that directory).

### 1. Host dependencies

Full system-package/Livox-SDK2/Sophus/vikit_common prerequisites are
documented in [FAST-LIVO2/README_ROS2.md](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/README_ROS2.md) —
[scripts/install_deps.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/install_deps.sh) automates exactly those
commands; run it once (needs sudo, safe to re-run):

```bash
./scripts/install_deps.sh
```

### 2. Apply the Intel patches

```bash
cd FAST-LIVO2
git am --keep-cr ../patches/0001-Stop-VIO-waiting-on-the-LiDAR-buffer-in-LIVO-mode.patch
git am --keep-cr ../patches/0002-Port-to-ROS2-and-bring-up-Mid-360-D415-on-A2W.patch
git am --keep-cr ../patches/0003-Size-OMP-thread-count-from-runtime-CPU-affinity.patch
git am --keep-cr ../patches/0004-Reformat-sources-to-the-real-clang-format-style.patch
git am --keep-cr ../patches/0005-Fix-crash-race-risks-and-an-info-leak-in-the-ROS2-no.patch
cd ..
```

(`git am` fails on a dirty or already-patched tree — `apply_patches.sh`'s
extra safety is only needed if you're re-running this against an edited
`.patch` file.)

### 3. Build with colcon

```bash
mkdir -p ~/fast_livo2_ws/src
ln -sfn "$(pwd)/FAST-LIVO2" ~/fast_livo2_ws/src/fast_livo2
source /opt/ros/jazzy/setup.bash

cd ~/fast_livo2_ws
colcon build --packages-select fast_livo2   # add --cmake-args -DENABLE_PERFRAME_TIMING=ON for the latency CSV
source install/setup.bash
cd -
```

If you don't already have `livox_ros_driver2`/`vikit_ros` built elsewhere,
point `UNDERLAY_SETUP` in [scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh) at an existing
install space, or let `scripts/build.sh` build them from scratch instead of
doing so by hand here.

### 4. Fetch and convert the NTU VIRAL sequence (`eee_01`)

The ROS1 `.bag` is served straight from NTU's Dataverse REST API (file id
`68133` for `eee_01`), no login required; ground truth comes from the
`viral_eval` GitHub repo:

```bash
mkdir -p ~/ntu_viral_dataset && cd ~/ntu_viral_dataset
curl -fL -o eee_01.zip https://researchdata.ntu.edu.sg/api/access/datafile/68133
unzip -p eee_01.zip "$(unzip -Z1 eee_01.zip | grep -E '\.bag$' | head -1)" > eee_01.bag
rm -f eee_01.zip
curl -fL -o leica_pose_eee_01.csv \
  https://raw.githubusercontent.com/ntu-aris/viral_eval/master/result_eee_01/leica_pose.csv
cd -
```

Then convert the ROS1 bag to ROS 2 with `rosbags-convert` (installed via
pip if missing):

```bash
python3 -c "import rosbags" 2>/dev/null || pip install --user --break-system-packages rosbags
PATH="${HOME}/.local/bin:${PATH}" rosbags-convert \
  --src ~/ntu_viral_dataset/eee_01.bag --dst ~/ntu_viral_dataset/eee_01
sed -i 's#type: livox_ros_driver/msg/CustomMsg#type: livox_ros_driver2/msg/CustomMsg#' \
  ~/ntu_viral_dataset/eee_01/metadata.yaml
```

(Other sequences' Dataverse file ids are listed in
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh)'s `ntu_viral_datafile_id()`; or just run
`./scripts/fetch_ntu_viral.sh`, which automates this whole step.)

### 5. Run `fast_livo2` against the bag

`NTU_VIRAL.yaml`'s tracked `evo/seq_name` param (which controls the output
trajectory filename, `Log/result/<seq_name>.txt`) already defaults to
`eee_01`, so no scratch-copy/`sed` step is needed — run directly against the
checked-in config.

Two terminals. **Terminal A — the algorithm:**

```bash
source /opt/ros/jazzy/setup.bash
source ~/fast_livo2_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=199

ros2 launch fast_livo2 mapping_ouster_ntu.launch.py \
  use_rviz:=false \
  avia_params_file:=FAST-LIVO2/config/NTU_VIRAL.yaml
```

**Terminal B — bag playback** (start once Terminal A is up and printing):

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=199

ros2 bag play ~/ntu_viral_dataset/eee_01
```

Once playback finishes, stop `fast_livo2` (`Ctrl-C` in Terminal A — a clean
SIGTERM, not `kill -9`, so it flushes the trajectory file) and check
`FAST-LIVO2/Log/result/eee_01.txt` was written. The core-pinning/SCHED_FIFO
wrapping `run_ntu_viral.sh` applies on PTL (taskset/chrt) is an optional
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

Verify with `ros2 node list` (should show the FAST-LIVO2 node within ~1s of
launching it). When done: stop `fast_livo2`/`ros2 bag play`, then
`pkill -x iox-roudi`.

### 6. Evaluate RMSE

The estimated trajectory (`FAST-LIVO2/Log/result/eee_01.txt`) needs
converting to the surveyed PRISM reflector frame before comparing against
ground truth — [evaluate_viral.py](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/Log/result/ntu_viral/evaluate_viral.py),
already checked into the repo, provides both conversions:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "FAST-LIVO2/Log/result/ntu_viral")
from evaluate_viral import convert_slam_to_prism, convert_leica_to_tum
convert_slam_to_prism("FAST-LIVO2/Log/result/eee_01.txt",
                       "FAST-LIVO2/Log/result/ntu_viral/eee_01_prism_repro.txt")
convert_leica_to_tum("$HOME/ntu_viral_dataset/leica_pose_eee_01.csv",
                      "FAST-LIVO2/Log/result/ntu_viral/eee_01_gt_repro.txt")
PY

pip install --user --break-system-packages evo   # if not already installed
PATH="${HOME}/.local/bin:${PATH}" evo_ape tum \
  FAST-LIVO2/Log/result/ntu_viral/eee_01_gt_repro.txt \
  FAST-LIVO2/Log/result/ntu_viral/eee_01_prism_repro.txt -a
```

`evo_ape`'s summary table reports RMSE in meters; multiply by 100 to compare
against the documented `eee_01` baseline of **2.71 cm**
([FAST-LIVO2/Log/result/ntu_viral/README.md](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c0346107b75b59934975adec9a6eeeb913c64/Log/result/ntu_viral/README.md)).
A fresh measurement that does not exceed the baseline by more than
`RMSE_TOLERANCE_PCT` (20% by default,
[scripts/env.sh](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/pipelines/fast-livo2-demo/scripts/env.sh)) is an expected pass — the check
exists to catch regressions, not to require beating the paper's own number.

## Limitations / non-goals

- Validated here: functional SLAM operation and pose-tracking accuracy
  (RMSE) against the public NTU VIRAL baseline.
- Sensor assumption: a synchronized LiDAR + camera + IMU stream (native
  Livox format for the Mid-360 profile, or a standard rosbag as in the NTU
  VIRAL flow above).
- Real-robot bring-up (Mid-360 + D415 on A2W) uses the config shipped in
  patch 0002 (`config/mid360-a2w*.yaml`) but requires that physical hardware
  and is not exercised by this reproduce flow.
- GPLv2 licensing (see callout above) applies to the upstream code as-is;
  this integration does not change that.
