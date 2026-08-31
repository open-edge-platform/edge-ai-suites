# GEAR-SONIC Introduction

SONIC is a humanoid behavior foundation model that gives robots a core set of motor skills learned from large-scale human motion data. Rather than building a separate controller for each predefined motion, SONIC treats motion tracking as a scalable training task, enabling a single unified policy to produce natural, whole-body movement and to support a wide range of behaviors — from walking and crawling to teleoperation and multi-modal control.

This repository extends the open-source [GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl.git) project and implements a comprehensive optimization of the SONIC whole-body-control (WBC) inference pipeline on the Intel Core Ultra "Panther Lake" (PTL) platform, including OpenVINO inference acceleration, a real-time control thread design, and priority-based NPU scheduling. It demonstrates that the PTL platform can meet SONIC WBC's determinism requirements while achieving substantial power savings compared to GPU execution.

## Prerequisites

- Follow the [Getting Started guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/platform_foundation/getting_started.html) to set up the base system.
- NPU driver (> v1.32.0)
- Ubuntu 24.04 RT release
- OpenVINO 2026.3, ROS2 Jazzy

For optimal NPU inference performance, it is recommended to use the latest NPU driver(e.g. v1.35.0) available from the [linux-npu-driver](https://github.com/intel/linux-npu-driver/releases) repository.

For OpenVINO, this project recommends installing from the archive file. Follow [Install OpenVINO from an Archive File (Linux)](https://docs.openvino.ai/2026/get-started/install-openvino/install-openvino-archive-linux.html), download the latest OpenVINO package, and extract it to the `/opt/intel/<openvino_version>` folder, e.g. `/opt/intel/openvino_2026.3.0`.

## Installation

This project extends the open-source GR00T-WholeBodyControl project to add OpenVINO acceleration and SONIC WBC pipeline optimizations for the Intel Core Ultra Panther Lake platform. Set up the environment with the following steps.

### 1. Initialize and patch the submodule
```bash
git submodule update --init <GR00T-WholeBodyControl>
cd <GR00T-WholeBodyControl>
git lfs pull          # make sure all large files are fetched
```

### 2. Apply the patches
```bash
git am --whitespace=fix ../patches/*.patch
```

### 3. Model preparation

```bash
python3 download_from_hf.py
```

This downloads the default deployment models — planner, encoder, and decoder — into `gear_sonic_deploy/`.

> **Tip:** If the download fails or stalls due to a proxy/network issue reaching Hugging Face, try switching to a mirror endpoint before re-running the script:
> ```bash
> export HF_ENDPOINT="https://hf-mirror.com"
> ```

### 4. Build

Set up the build environment and build the project:

```bash
cd gear_sonic_deploy
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh

source gear_sonic_deploy/scripts/setup_env.sh
cd gear_sonic_deploy
just build
```

`setup_env.sh` auto-detects your OpenVINO installation and sets `USE_OPENVINO=1`, so the build links against OpenVINO instead of CUDA/TensorRT.

## Basic Tests: Run SONIC with MuJoCo

### One-time setup

From the repo root, install the MuJoCo simulator environment:

```bash
bash install_scripts/install_mujoco_sim.sh --ov
```

This creates a lightweight `.venv_sim` virtual environment with only the packages needed for the simulator (MuJoCo, Unitree SDK2, etc.).

> **Tip:** Suggest run the MuJoCo simulator on a local display, not over a remote connection (SSH X11 forwarding, remote desktop, etc.). Remote rendering adds its own latency/jitter, which can make a correct motion (walking, running, dancing) look wrong.

### Run the basic SONIC test

**Terminal 1 — MuJoCo simulator:**

```bash
source .venv_sim/bin/activate
python gear_sonic/scripts/run_sim_loop.py
```

**Terminal 2 — Deployment:**

```bash
cd gear_sonic_deploy
bash deploy.sh sim
```

### Starting control

1. In Terminal 2 (`deploy.sh`), press `]` to start the policy.
2. Click on the MuJoCo viewer window, then press `9` to drop the robot to the ground.
3. Go back to Terminal 2. Press `T` to play the current reference motion — the robot executes it to completion.
4. Press `N` or `P` to switch to the next or previous motion sequence. Press `T` again to play the new motion.
5. When you are done, or need an emergency stop, press `O` to stop control and exit.
6. Press `Enter` to toggle planner mode.
7. In planner mode, use `N` or `P` to switch between motion modes (`IDLE`, `SQUAT`, `BOXING`, `LEDGE_WALKING`, etc.).
8. In `IDLE` or `LEDGE_WALKING` mode, use the keys below to control the robot.

**Planner mode keys** (toggle planner mode with `Enter`):

| Key | Action |
|---|---|
| W / S | Move forward / backward |
| A / D | Adjust heading slightly and move forward (left / right) |
| Q / E | Turn in place — adjust facing direction only, no forward motion (±30° per press) |
| 1–8 | Select a locomotion mode from the current motion set |
| N / P | Next / previous motion set |
| 9 / 0 | Decrease / increase speed |
| T | Play motion |

For the full control reference — including Normal Mode, all motion sets, and the momentum system — see `docs/source/tutorials/keyboard.md`.

### Checking Model Performance

Once control is running, the deploy log periodically prints a `Loop timing` line with running latency stats (in microseconds) for the control loop:

```text
Loop timing - ... Obs: 645us (avg:689 min:460 P99:907 max:1023), Policy: 405us (avg:405 min:306 P99:618 max:723), ...
```

- **Obs** — gathering observations for the current tick plus running the encoder.
- **Policy** — pure decoder inference time.

In planner mode, an added `Planner` block reports the planner model's own latency the same way, e.g. `Model: 15403us (avg:15304 min:14895 P99:16292 max:17895)`.

Use these numbers to confirm real-time deadlines are met and to compare latency across NPU priority/turbo settings (see [NPU Inference Configuration](#npu-inference-configuration) below).

## NPU Inference Configuration

The `inference:` section of [`gear_sonic_deploy/policy/release/observation_config.yaml`](../gear_sonic_deploy/policy/release/observation_config.yaml) controls how the encoder, policy, and planner models are scheduled on the NPU:

- **NPU priority** (`encoder_priority` / `policy_priority` / `planner_priority`): `HIGH`, `NORMAL`, or `LOW`. Controls how the OpenVINO scheduler arbitrates models that share the same NPU device (mapped to `ov::hint::model_priority`). Encoder and policy default to `HIGH` since they run on the real-time control thread; the planner defaults to `NORMAL`.
- **NPU turbo mode** (`npu_turbo`): when `true`, applies `NPU_TURBO=YES` to all NPU models, trading power efficiency for lower inference latency. Recommended on for real-time control; set to `false` to save power/thermal headroom. This is an NPU-only hint and is ignored on CPU/GPU.

### Verifying the Inference Device

To confirm which device a model landed on, watch the deploy log during model init (encoder, policy, planner) — before `Starting control` is printed. Each NPU model logs:

```text
[OVInference] Requested device: NPU
[OVInference] Model priority: HIGH
```

Encoder and policy should show `HIGH` priority; the planner should show `NORMAL`.
