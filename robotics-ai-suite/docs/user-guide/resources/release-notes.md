# Release Notes: Robotics AI Suite 2026.2

**Release Date**: September 9, 2026

## Autonomous Mobile Robot

**Improved**:

- Added opt-in per-stage latency profiling (lock-free ring buffer with a dedicated writer thread, using `CLOCK_MONOTONIC` to stay immune to PTP clock steps) behind CMake build options, off by default to match upstream.
- Hardened the ported SLAM sources with mutex/locking corrections around shared LiDAR/IMU buffers, division-by-zero and out-of-bounds guards, `main()` try/catch wrapping, and removal of an internal-lab IP address from a configuration comment (BDBA information-leakage finding).
- `ros-kpi`: Streamlined the benchmarking component and its packaging.

## Humanoid Toolkit

This release extends humanoid support to the Intel® Core™ Ultra Series 3 "Panther Lake" (PTL) platform, introduces NVIDIA Isaac-GR00T foundation-model pipelines accelerated with the OpenVINO™ toolkit, and adds three new LiDAR-based SLAM back-ends for mobile robot localization and mapping, each shipped as a pristine upstream git submodule with Intel changes applied as patches, so they can be evaluated as alternative back-ends without forking the reference navigation stack. All three are validated by replaying public datasets and include reference Intel® Core™ Ultra "Panther Lake" (PTL) core-pinning and frequency-locking scripts plus opt-in per-stage latency profiling.

**New**:

- **LIO SLAM: FAST-LIO2** — Added a computationally efficient, tightly-coupled LiDAR-Inertial Odometry pipeline (`fast-lio2-demo`) ported to ROS 2 Jazzy on Ubuntu 24.04. Includes new LiDAR configurations, a configurable OpenMP thread count sized from runtime CPU affinity, a preprocessing crash fix for Velodyne scans missing a `time` field, and validation via public NCLT dataset replay.
- **LIVO SLAM: FAST-LIVO2** — Added a direct (feature-less) LiDAR-Inertial-Visual Odometry pipeline (`fast-livo2-demo`) that fuses LiDAR-inertial pose estimation with dense visual-inertial tracking for robustness in geometrically- or visually-degraded environments. Ported from ROS 1/catkin to ROS 2 (validated on Humble and Jazzy), with a Livox Mid-360 + Intel® RealSense™ D415 sensor profile and validation via public NTU VIRAL dataset replay.
- **LIO SLAM: Point-LIO** — Added a high-bandwidth, robust LiDAR-Inertial Odometry pipeline (`point-lio-demo`) using a point-by-point EKF update (no in-frame motion distortion) and a stochastic-process-augmented kinematic model that tolerates IMU saturation during aggressive motion. Ported to ROS 2/ament with new Avia, Mid-360, and Velodyne configurations and validation via public UrbanLoco dataset replay.
- **GR00T N1.7 (OpenVINO Toolkit)** — Added `gr00t-n1d7-ov`, an implementation of the NVIDIA Isaac-GR00T N1.7 embodied AI foundation model for robot manipulation and generalist control, with an end-to-end pipeline that accelerates inference on Intel platforms via OpenVINO IR model conversion. Includes a LIBERO finetuned-checkpoint workflow for convenient evaluation.
- **GEAR-SONIC Whole-Body Control** — Added `gr00t-wbc`, a comprehensive optimization of the SONIC humanoid whole-body-control (WBC) inference pipeline on the Intel® Core™ Ultra "Panther Lake" platform. SONIC is a behavior foundation model that produces natural, whole-body movement (walking, crawling, teleoperation, multi-modal control) from a single unified policy. The pipeline adds OpenVINO inference acceleration, a real-time control thread design, and priority-based NPU scheduling, demonstrating that Intel® Panther Lake (PTL) can meet SONIC WBC's determinism requirements with substantial power savings compared to GPU execution (OpenVINO 2026.3, ROS 2 Jazzy, Ubuntu 24.04 RT).

**Improved**:

- **Model Predictive Control (MPC) demo** — Updated the OCS2-based MPC pipeline (ACT reference model + OCS2 optimization + MuJoCo simulation) documentation and setup for the 2026.2 platform.
- Added reference Intel® Core™ Ultra "Panther Lake" core-pinning and CPU frequency-locking scripts and reproducible one-command validation flows (`reproduce_all.sh`) across the new SLAM pipelines for deterministic, comparable benchmarking.
- Refreshed the imitation-learning and VLA sample pipelines (ACT, Diffusion Policy, Improved 3D Diffusion Policy, Pi0.5 with Real-Time Chunking, Robotics Diffusion Transformer, LLM Robotics, OpenClaw + AgenticROS, ORB-SLAM3) for the 2026.2 documentation and platform references.

<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2026.1 <./release-notes/release-2026.1.md>
Release Notes 2026.0 <./release-notes/release-2026.0.md>
Release Notes 25.36 <./release-notes/release-25.36.md>
Release Notes 25.15 <./release-notes/release-25.15.md>

:::
hide_directive-->