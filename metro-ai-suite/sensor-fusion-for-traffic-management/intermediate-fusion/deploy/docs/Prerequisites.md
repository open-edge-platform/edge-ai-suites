# Host Prerequisites

This guide explains how to prepare an Ubuntu host for a native build and run of this project. If you only want to validate the project, prefer the published Docker image in `../docker/README_Docker.md`; after installing Docker Engine and the host driver packages, you can skip the native dependency installation and local build steps below.

## Supported Environment

| Component | Version |
| --- | --- |
| Base OS | Ubuntu 24.04 |
| oneAPI | `2025.3` |
| Custom OpenVINO | `2026.1.0` |
| Intel GPU compute runtime | `26.14.37833.4` |
| Intel Graphics Compiler | `2.32.7+21184` |
| GMM | `22.9.0` |
| Level Zero loader | `1.28.2+u24.04` |
| Intel NPU driver | `v1.32.1.20260422-24767473183` |
| xpu-smi | `v1.3.6` |
| Boost | `1.83.0` |
| OpenCL-SDK | `v2025.07.23` |

## 1. Before You Start

- Use Ubuntu 24.04 x86_64.
- Make sure `sudo` is available.
- Expect at least one Intel GPU.
- If the driver script upgrades the kernel or installs NPU packages, reboot before continuing.
- Run all commands from the deployment project root unless noted otherwise.

## 2. Install Driver-Related Packages

```bash
bash install_driver_related_libs.sh
```

The script installs the GPU runtime packages, media stack, monitoring tools, and NPU packages when supported hardware is present.

Useful environment variables:

- `SKIP_KERNEL_UPGRADE=1`: keep the current kernel.
- `SKIP_NPU_DRIVER=1`: skip the NPU path.
- `SKIP_XPU_SMI=1`: skip xpu-smi installation.
- `KEEP_BUILD_DIR=1`: keep the temporary download directory under `$HOME/3rd_build`.

After the script completes:

- Reboot if the script asks for it.
- Refresh group membership with `newgrp render` or log out and back in.
- Use `xpu-smi` or `clinfo` to confirm that the GPU is visible.

## 3. Optional: Validate With The Published Docker Image

If you only need a smoke test of the project, install Docker Engine and Docker Compose by following `../docker/README_Docker.md`, then use the published image:

```bash
docker pull tfcc:bevfusion
bash autotest_docker.sh --image tfcc:bevfusion
```

To open an interactive shell in the published image:

```bash
bash docker/run_docker.sh tfcc:bevfusion
```

If this container workflow is sufficient, you do not need to continue with the native dependency installation below.

## 4. Native Host Build: Install Project Dependencies

```bash
bash install_project_related_libs.sh
```

The script installs the build toolchain, runtime libraries, Boost, oneAPI, OpenCL-SDK, and custom OpenVINO under `/opt/intel/openvino`.

Useful environment variables:

- `USE_SYSTEM_BOOST=1`: use Ubuntu Boost packages.
- `SKIP_ONEAPI=1`: skip oneAPI installation when it is already present.
- `SKIP_OPENVINO=1`: skip the custom OpenVINO installation when it is already present.
- `SKIP_OPENCL_SDK=1`: skip the OpenCL-SDK build.

## 5. Source The Runtime Environment

Use the following commands in each new shell:

```bash
source /opt/intel/oneapi/setvars.sh
source /opt/intel/openvino/setupvars.sh
```

## 6. Build The Project

```bash
bash build.sh
```

The build output is written to `build/`.

## 7. Check The Dataset Layout

Expected layout:

```text
<dataset_root>/
  calib/
  image_2/
  label_2/
  velodyne/
```

Supported input file types:

- `image_2`: `.jpg`, `.jpeg`, `.png`, or encoded `.bin`
- `velodyne`: `.bin` or `.pcd`
- `calib`: `.txt`
- `label_2`: `.txt`

Encoded `.bin` image files are supported by the loader.

## 8. Smoke Test The Native Environment

From `build/`:

```bash
./test_bev_pool 1 5
./bevfusion ../data/v2xfusion/dataset
```

Typical successful output includes:

```text
Using discrete OpenCL GPU (in-order queue): Intel(R) Arc(TM) B580 Graphics
=== BEVPool Latency ===
Avg: 0.693 ms
```

```text
Detected 0 boxes
[perf] frames=1, avg_lidar=7.463 ms, avg_camera_bev=8.703 ms, avg_fusion+post=3.979 ms, avg_total=12.685 ms
```

The bundled release models are dummy weights, so `Detected 0 boxes` is expected in this smoke check. Use your own exported weights if you need meaningful detections.

If the native smoke tests pass, continue with `GSG.md` and `Testing.md`.