# Getting Started Guide

This guide covers two workflows:

- Recommended: run the published Docker image.
- Optional: build and run the project natively on the host.

## 1. Recommended Quick Run In Docker

Follow `../docker/README_Docker.md` to install Docker Engine, Docker Compose, and the required host driver packages. Then pull and test the published image:

```bash
docker pull intel/tfcc:bevfusion
bash autotest_docker.sh --image intel/tfcc:bevfusion
```

The published image keeps the `intel/tfcc:bevfusion` name after pull. If you want the shorter local tag used by some helper defaults, add it yourself:

```bash
docker tag intel/tfcc:bevfusion tfcc:bevfusion
```

To inspect the image or run the binaries interactively:

```bash
bash docker/run_docker.sh intel/tfcc:bevfusion
docker exec -it <container id> /bin/bash

cd build
./bevfusion ../data/v2xfusion/dataset
./bevfusion_unified ../data/v2xfusion/dataset --num-samples 1
```

If this container workflow is enough for your use case, you can stop here.

The bundled model files under `../data/*/pointpillars` and `../data/*/second` are dummy weights in the current release package. They preserve the runtime interfaces so the applications can be launched and profiled, but they do not produce meaningful detections or evaluation results.

## 2. Prepare The Host For A Native Build

```bash
bash install_driver_related_libs.sh
bash install_project_related_libs.sh
```

See `Prerequisites.md` for the full environment requirements, package versions, and optional environment variables.

## 3. Build The Project

Recommended build command:

```bash
bash build.sh
```

Equivalent manual flow:

```bash
source /opt/intel/oneapi/setvars.sh
source /opt/intel/openvino/setupvars.sh

mkdir -p build
cd build
cmake ..
cmake --build . --parallel "$(nproc)"
```

## 4. Run `bevfusion`

From `build/`:

```bash
./bevfusion <dataset_path> [--preset v2x|kitti] [--model-dir DIR] \
    [--fp32] [--int8] [--int8-camera] [--int8-pfe] [--int8-fuser] [--int8-head] \
    [--vis] [--save-image] [--save-video] [--display] [--util] \
    [--repeat N] [--num-samples N] [--dump-pred] [--pred-dir DIR] \
    [--vis-dir DIR] [--device DEVICE] \
    [--filter-labels NAME,...] [--no-filter]
```

Important options:

- `<dataset_path>`: KITTI-style dataset root.
- `--preset v2x|kitti`: select DAIR-V2X or KITTI-360 geometry and post-process settings.
- `--model-dir DIR`: override the default split-model directory. The default is `../data/v2xfusion/pointpillars` for `v2x` and `../data/kitti/pointpillars` for `kitti`.
- Default behavior requests all available INT8 component models. On Battlemage GPUs, the split pipeline uses `fuser.onnx` instead of `quantized_fuser.xml` for the known INT8 fuser issue.
- PFE selection uses `quantized_lidar_pfe.xml` for INT8. FP32 runs prefer `lidar_pfe_v7000.onnx` and fall back to `lidar_pfe_v6000.onnx` when v7000 is not present.
- `--fp32`: switch all split components to FP32 ONNX models.
- `--int8`: explicitly use all available INT8 component models.
- `--repeat N`: run the dataset multiple times.
- `--num-samples N`: limit the run to the first `N` discovered samples.
- `--dump-pred --pred-dir DIR`: export KITTI-format predictions.
- `--save-image`, `--save-video`, `--display`: enable visualization outputs.

Example commands:

```bash
./bevfusion ../data/v2xfusion/dataset
./bevfusion ../data/v2xfusion/dataset --fp32
./bevfusion ../data/kitti/dataset --preset kitti
./bevfusion ../data/kitti/dataset --preset kitti --fp32
```

With the bundled release assets, a successful runtime smoke run ends with output similar to:

```text
Detected 0 boxes
[perf] frames=..., avg_lidar=... ms, avg_camera_bev=... ms, avg_fusion+post=... ms, avg_total=... ms
```

## 5. Run `bevfusion_unified`

From `build/`:

```bash
./bevfusion_unified <dataset_path> [--preset v2x|kitti] [--model PATH] [--fp16] \
    [--vis] [--save-image] [--save-video] [--display] [--util] \
    [--repeat N] [--num-samples N] [--dump-pred] [--pred-dir DIR] \
    [--vis-dir DIR] [--recompute-camera-metas] [--cache-camera-metas] \
    [--filter-labels NAME,...] [--no-filter]
```

Important options:

- `<dataset_path>`: KITTI-style dataset root.
- `--preset v2x|kitti`: select DAIR-V2X or KITTI-360 geometry, voxelization range, post-process range, and camera metadata policy.
- Default behavior loads the dataset-specific INT8 OpenVINO IR from `../data/<dataset>/second/bevfusion_unified_int8.xml`.
- `--fp16`: switch to the dataset-specific FP16 ONNX model at `../data/<dataset>/second/bevfusion_unified_fp16.onnx`.
- `--model PATH`: override the default model path. `--onnx PATH` remains accepted as a compatibility alias.
- `--recompute-camera-metas`: recompute camera geometry for every frame.
- `--cache-camera-metas`: compute camera geometry once and reuse it. This is the V2X default; KITTI defaults to per-frame recompute.
- `--num-samples N`: limit the run to the first `N` discovered samples.
- `--repeat N`: repeat the selected samples.
- `--dump-pred --pred-dir DIR`: export KITTI-format predictions.
- `--save-image`, `--save-video`, `--display`: enable visualization outputs.

Example commands:

```bash
./bevfusion_unified ../data/v2xfusion/dataset --num-samples 1
./bevfusion_unified ../data/v2xfusion/dataset --fp16 --num-samples 1
./bevfusion_unified ../data/kitti/dataset --preset kitti --num-samples 1
```

With the bundled release assets, a successful runtime smoke run ends with output similar to:

```text
[info] 1 samples
    000000: 0 boxes
[perf] frames=1, avg_voxelize=4.523 ms, avg_preprocess=0.721 ms, avg_geometry=0.000 ms, avg_infer=31.422 ms, avg_postprocess=1.587 ms, avg_total=38.253 ms
```

## 6. Save Results And Visualizations

Both main applications support the same result-export workflow:

- `--save-image`: save per-frame visualization images.
- `--save-video`: save a video file.
- `--display`: open a live preview window when a GUI environment is available.
- `--dump-pred --pred-dir <dir>`: write KITTI-format prediction files for evaluation.

## 7. Accuracy Evaluation

Generate predictions with either main application and then run the evaluation helper.

Split pipeline example:

```bash
cd build
./bevfusion <dataset_path> --dump-pred --pred-dir pred_split
```

Unified pipeline example:

```bash
cd build
./bevfusion_unified <dataset_path> --dump-pred --pred-dir pred_unified
```

Evaluation command:

```bash
python3 ../tools/kitti_3d_eval.py \
    --gt <dataset_path>/label_2 \
    --pred ./pred_split \
    --out eval_output \
    --max-distance 102.4 \
    --z-center-gt
```

## 8. Performance Testing

Use a representative dataset and run the main applications without visualization when measuring latency.

```bash
./bevfusion <dataset_path>
./bevfusion_unified <dataset_path> --num-samples N
./bevfusion_unified <dataset_path> --fp16 --num-samples N
```

Successful runs end with a `[perf]` summary. For the split pipeline the summary includes lidar, camera, fusion, and total latency. For the unified pipeline the summary includes voxelization, preprocess, inference, postprocess, and total latency. Default runs use INT8 models; add `--fp32` for split-model FP32 comparison or `--fp16` for unified FP16 comparison.

## 9. Troubleshooting

### Missing `libsycl.so.8`

Source oneAPI before running the binaries:

```bash
source /opt/intel/oneapi/setvars.sh
source /opt/intel/openvino/setupvars.sh
```

### `No samples found in dataset`

- Verify that the dataset root contains `image_2`, `velodyne`, `calib`, and `label_2`.
- Keep sample IDs zero-padded to six digits.
- Keep the original file extensions when preparing a dataset copy.

### `Failed to decode image from bin file`

Encoded `.bin` image files are decoded through OpenCV. If decoding fails, verify that the file contains a valid encoded image.

### GPU runtime issues

- Re-run `bash install_driver_related_libs.sh` after a reboot if the script upgraded the kernel.
- Refresh group membership with `newgrp render` or log out and back in.
- Use `xpu-smi` and `clinfo` to confirm that the target GPU is visible before running inference.

## 10. More Detail

Use `Testing.md` for the full executable reference and sample output patterns. Use `../docker/README_Docker.md` for the container workflow.