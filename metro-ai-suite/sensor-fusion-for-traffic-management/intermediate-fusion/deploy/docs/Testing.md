# Executable Reference

This document describes the executables built under `build/`, their parameters, and the output to expect from a successful run.

For KITTI-format evaluation after inference, see `../tools/README_eval.md`.

For the quickest end-to-end run, prefer the published Docker image:

```bash
docker pull tfcc:bevfusion
bash autotest_docker.sh --image tfcc:bevfusion
```

## Common Runtime Setup

From a fresh shell in a native build, or after entering the container interactively:

```bash
source /opt/intel/oneapi/setvars.sh
source /opt/intel/openvino/setupvars.sh
cd build
```

Useful data locations:

- `../data/v2xfusion/dataset`: sample dataset for smoke tests.
- `../data/kitti/dataset`: KITTI-360 sample dataset for smoke tests.
- `../data/v2xfusion/pointpillars` and `../data/kitti/pointpillars`: split-model assets for `bevfusion`.
- `../data/v2xfusion/second` and `../data/kitti/second`: unified-model assets for `bevfusion_unified`.
- `../data/v2xfusion/dump_bins`: pre-dumped tensors used by several module tests.
- `<dataset_path>`: your KITTI-style dataset root.

## Automated Smoke Test

Use the helper script to run all deploy binaries in one pass, collect per-binary logs, count pass/fail results, and print the final `[perf]` summaries for `bevfusion` and `bevfusion_unified`.

```bash
bash autotest.sh
```

To run against your own KITTI-style dataset:

```bash
bash autotest.sh --dataset-path /path/to/kitti_dataset
```

Verbose live-output mode:

```bash
bash autotest.sh --verbose
```

To change the per-case timeout:

```bash
bash autotest.sh --case-timeout 120
```

Notes:

- Without `--dataset-path`, the script uses `data/v2xfusion/dataset` and runs the dataset-based binaries on a temporary one-frame mini dataset built from the first sample.
- In the default sample mode, `bevfusion` and `bevfusion_unified` also run on that mini dataset, and their repeat controls remain available.
- With `--dataset-path`, `bevfusion` and `bevfusion_unified` run on the provided dataset path.
- In explicit dataset mode, `--bevfusion-repeat` and `--unified-repeat` are ignored.
- If `../data/model_asset_mode.txt` declares `mode=dummy`, `autotest.sh` switches to runtime smoke mode and only runs the `bevfusion` / `bevfusion_unified` application checks. The bundled release assets currently use dummy weights, so module and development tests are intentionally excluded from the default smoke flow.
- The dataset-based `test_*` binaries still use a temporary mini dataset built from the first sample.
- Module tests such as `test_bev_pool`, `test_fuser`, and `test_head` use short warmup and iteration counts by default.
- Every test case has a default 120-second timeout. A timeout is recorded as a failed case and the script continues to the final summary. Use `--case-timeout 0` only when you intentionally want no timeout.
- Logs and the summary file are written under `build/autotest_logs/<timestamp>/` unless `--logs-dir` is provided.
- The default console mode is quiet: only start/finish status lines plus the final summary are printed.
- `--verbose` restores per-binary live output while still keeping the same log files.
- The final console line is `AUTOTEST_RESULT ...`, which includes pass/fail/skipped counts and the log and summary paths.

## Docker Automated Smoke Test

Use the Docker helper when you want to run the deploy workflow inside the container image.

If you already pulled the published image:

```bash
bash autotest_docker.sh --image tfcc:bevfusion
```

To run the container autotest on a dataset stored on the host:

```bash
bash autotest_docker.sh --image tfcc:bevfusion --dataset-path /path/to/kitti_dataset
```

If you already pulled or built the default image tag `tfcc:bevfusion`, you can omit `--image`.

If the image must be built first:

```bash
bash autotest_docker.sh \
  --build-image \
  --custom-openvino-install-dir /path/to/custom_openvino/install
```

Notes:

- The Docker helper uses `docker/run_docker.sh`, so GPU and X11 settings match the documented container workflow.
- If you already pulled or built a suitable image locally, the helper does not need to rebuild it.
- Without `--dataset-path`, it runs `autotest.sh` inside the container against the bundled sample dataset path.
- With `--dataset-path`, the script copies the host dataset into the container before the run and points the inner autotest command at that copied dataset.
- Container logs are copied back to `docker_autotest_logs/<timestamp>/` unless `--host-logs-dir` is provided.
- The final console line is `AUTOTEST_DOCKER_RESULT ...`, which reports pass/fail/skipped counts and the copied host log paths.

## Main Applications

### `bevfusion`

Purpose: run the split-model end-to-end deployment pipeline.

Usage:

```bash
./bevfusion <dataset_path> [--preset v2x|kitti] [--model-dir DIR] \
  [--fp32] [--int8] [--int8-camera] [--int8-pfe] [--int8-fuser] [--int8-head] \
  [--vis] [--save-image] [--save-video] [--display] [--util] \
  [--repeat N] [--num-samples N] [--dump-pred] [--pred-dir DIR] \
  [--vis-dir DIR] [--device DEVICE] \
    [--filter-labels NAME,...] [--no-filter]
```

Key parameters:

- `<dataset_path>`: KITTI-style dataset root.
- `--preset v2x|kitti`: select model geometry and post-process geometry.
- `--model-dir DIR`: override the decoupled split-model directory.
- Default behavior requests all available INT8 component models. On Battlemage GPUs, the split pipeline uses `fuser.onnx` instead of `quantized_fuser.xml` for the known INT8 fuser issue.
- PFE selection prefers `lidar_pfe_v7000.onnx` and falls back to `lidar_pfe_v6000.onnx` for FP32 runs. INT8 PFE uses `quantized_lidar_pfe.xml` with the v7000 voxel count.
- `--fp32`: switch all split components to FP32 ONNX models.
- `--int8`: explicitly use all available INT8 component models.
- `--repeat N`: run the dataset multiple times.
- `--num-samples N`: limit the run to the first `N` discovered samples.
- `--dump-pred --pred-dir DIR`: write KITTI-format predictions.
- `--save-image`, `--save-video`, `--display`: enable visualization output.

Example command:

```bash
./bevfusion ../data/v2xfusion/dataset
```

When you use the bundled release assets, successful runtime smoke output typically includes:

```text
Detected 0 boxes
[perf] frames=..., avg_lidar=... ms, avg_camera_bev=... ms, avg_fusion+post=... ms, avg_total=... ms
```

The bundled release models are dummy weights, so `Detected 0 boxes` is expected and does not indicate a runtime failure. Use your own exported weights if you need meaningful predictions.

### `bevfusion_unified`

Purpose: run the unified end-to-end deployment pipeline.

Usage:

```bash
./bevfusion_unified <dataset_path> [--preset v2x|kitti] [--model PATH] [--fp16] \
    [--vis] [--save-image] [--save-video] [--display] [--util] \
    [--repeat N] [--num-samples N] [--dump-pred] [--pred-dir DIR] \
  [--vis-dir DIR] [--recompute-camera-metas] [--cache-camera-metas] \
  [--filter-labels NAME,...] [--no-filter]
```

Key parameters:

- `<dataset_path>`: KITTI-style dataset root.
- `--preset v2x|kitti`: select DAIR-V2X or KITTI-360 geometry, voxelization range, post-process range, and camera metadata policy.
- Default behavior loads the dataset-specific INT8 OpenVINO IR from `../data/<dataset>/second/bevfusion_unified_int8.xml`.
- `--fp16`: switch to the dataset-specific FP16 ONNX model at `../data/<dataset>/second/bevfusion_unified_fp16.onnx`.
- `--model PATH`: override the default model path. `--onnx PATH` remains accepted as a compatibility alias.
- `--recompute-camera-metas`: recompute camera geometry for every frame.
- `--cache-camera-metas`: compute camera geometry once and reuse it. This is the V2X default; KITTI defaults to per-frame recompute.
- `--num-samples N`: limit the run to the first `N` discovered samples.
- `--repeat N`: repeat the selected samples.
- `--dump-pred --pred-dir DIR`: write KITTI-format predictions.
- `--save-image`, `--save-video`, `--display`: enable visualization output.

Example commands:

```bash
./bevfusion_unified ../data/v2xfusion/dataset --num-samples 1
./bevfusion_unified ../data/v2xfusion/dataset --fp16 --num-samples 1
./bevfusion_unified ../data/kitti/dataset --preset kitti --num-samples 1
```

When you use the bundled release assets, successful runtime smoke output typically includes:

```text
[info] 1 samples
  000000: 0 boxes
[perf] frames=1, avg_voxelize=4.523 ms, avg_preprocess=0.721 ms, avg_geometry=0.000 ms, avg_infer=31.422 ms, avg_postprocess=1.587 ms, avg_total=38.253 ms
```

The bundled release models are dummy weights, so `0 boxes` is expected and does not indicate a runtime failure. Use your own exported weights if you need meaningful predictions.

## Module And Development Tests

These `test_*` binaries validate intermediate tensors, non-zero scatter buffers, or non-empty detections. They are useful with real models, but they are not part of the default smoke flow when `../data/model_asset_mode.txt` says `mode=dummy`.

### `test_bev_pool`

Purpose: isolate the BEVPool kernel and geometry indices.

Usage:

```bash
./test_bev_pool [warmup_iters=10] [iters=200]
```

Example command:

```bash
./test_bev_pool 1 5
```

Expected output includes:

```text
Geometry: num_intervals=7313, num_indices=466560
=== BEVPool Latency ===
Avg: 0.693 ms
Throughput: 1442.3 it/s
```

### `test_camera_geometry`

Purpose: check geometry creation, matrix updates, repeated updates, and cleanup.

Usage:

```bash
./test_camera_geometry
```

Expected output includes:

```text
=== Performance Benchmark ===
Average time per update: 0.293 ms
=== Test Summary ===
All tests passed!
```

### `test_viewtransform`

Purpose: run the camera backbone and view transform path from a single image and save intermediate outputs.

Usage:

```bash
./test_viewtransform <image_path> [model_path] [warmup] [iters] [--fp32]
```

Example command:

```bash
./test_viewtransform ../data/v2xfusion/dataset/image_2/000000.jpg
```

Expected output includes:

```text
Results saved:
  - BEV features: bev_camera_features.bin
  - Camera features: camera_features.bin
  - Camera depth weights: camera_depth_weights.bin
  - Indices: indices_output.bin
  - Intervals: intervals_output.bin
[perf] iters=100, avg=4.56098 ms, min=4.53343 ms, max=4.60392 ms
```

### `test_camera_bev_pipeline`

Purpose: run the camera branch over a dataset root and print camera-side timing information.

Usage:

```bash
./test_camera_bev_pipeline <dataset_path> [model_path] [warmup] [--fp32]
```

Key parameters:

- `<dataset_path>`: KITTI-style dataset root.
- `[model_path]`: optional camera model override.
- `[warmup]`: optional warmup count.
- `--fp32`: switch to the FP32 camera model.

Expected output includes:

```text
bev numel: ...
[perf] frames=..., avg_camera_bev=... ms, min=... ms, max=... ms
[perf] camera_bev avg_ms: geom=... ms, cam=... ms, bevpool=... ms, total=... ms
```

### `test_pointpillars_voxelizer`

Purpose: check the PointPillars raw-point voxelizer. With no arguments it runs a small synthetic correctness case that checks coordinate filtering, padding zeros, and output coordinates. It can also dump tensors for an external point-cloud binary.

Usage:

```bash
./test_pointpillars_voxelizer
./test_pointpillars_voxelizer --points POINTS.bin --num N [--dim 4] [--dump] [--out-dir DIR]
```

Expected output includes:

```text
voxelizer returned V=... (max=...)
Synthetic voxelizer check passed
```

### `test_pointpillars`

Purpose: run the decoupled lidar branch: raw points, voxelizer, 3-input PFE ONNX, and scatter.

Default PFE lookup uses `quantized_lidar_pfe.xml` for INT8, or `lidar_pfe_v7000.onnx` before `lidar_pfe_v6000.onnx` for FP32.

Usage:

```bash
./test_pointpillars --dataset DATASET_ROOT [--model-dir MODEL_DIR] [--pfe MODEL] [--int8|--fp32] [--dump] [--out-dir DIR]
./test_pointpillars --points POINTS.bin --num N --pfe MODEL [--dump] [--out-dir DIR]
```

Expected output includes:

```text
timing: pre=...ms  pfe=...ms  scatter=...ms
non_zero=... / ...
[perf] frames=1, avg_lidar=... ms
```

### `test_lidar_pipeline`

Purpose: run the canonical lidar wrapper over a dataset root. This covers `LidarBackbone`, PointPillars voxelization, PFE, scatter, and the `TensorView` device-output contract used by the fuser.

Default PFE lookup matches `test_pointpillars`: INT8 uses `quantized_lidar_pfe.xml`, while FP32 prefers `lidar_pfe_v7000.onnx` before `lidar_pfe_v6000.onnx`.

Usage:

```bash
./test_lidar_pipeline <dataset_path> [pfe_model] [warmup] [--num-samples N] [--fp32]
```

Expected output includes:

```text
scatter non_zero=... / ...
[perf] frames=..., avg_lidar=... ms, min=... ms, max=... ms
[perf] lidar avg_ms: pre=... ms, pfe=... ms, scatter=... ms, total=... ms
```

### `test_fusion_pipeline`

Purpose: run the fuser, head, and postprocess path with host-backed or USM-backed inputs.

Default fuser selection matches the split pipeline: it requests `quantized_fuser.xml`, but uses `fuser.onnx` on Battlemage GPUs for the known INT8 fuser issue.

Usage:

```bash
./test_fusion_pipeline [data_root] [warmup] [iters] [host|usm] [--fp32]
```

Example command:

```bash
./test_fusion_pipeline ../data/v2xfusion 1 5 usm
```

Expected output includes:

```text
[iter 5] total=4.19714 ms, boxes=27
=== Latency Summary ===
Mode: usm
[perf] fusion avg_ms: fuser=1.354 ms, head=1.031 ms, post=1.747 ms, total=4.131 ms (samples=5)
```

### `test_bevfusion_pipeline`

Purpose: run the canonical split-model pipeline class directly over a dataset root. This is the development smoke test for the same decoupled architecture used by `bevfusion`.

Usage:

```bash
./test_bevfusion_pipeline <dataset_path> [--preset v2x|kitti] [--model-dir DIR] [--num-samples N] [--warmup N] [--fp32]
```

Expected output includes:

```text
000000: ... boxes
[perf] frames=..., avg_lidar=... ms, avg_camera_bev=... ms, avg_fusion+post=... ms, avg_total=... ms
```

### `test_fuser`

Purpose: run the fuser network only with pre-dumped camera and lidar BEV tensors.

Default fuser selection matches the split pipeline: it requests `quantized_fuser.xml`, but uses `fuser.onnx` on Battlemage GPUs for the known INT8 fuser issue. Passing an explicit `fuser_model` keeps that model override.

Usage:

```bash
./test_fuser [warmup] [iters] [fuser_model] [cam_bev_bin] [lidar_scatter_bin] [--fp32]
```

Example command:

```bash
./test_fuser 1 5
```

Expected output includes:

```text
Sample fused values (first 10): 0.205688 0 0.0585327 0.138672 0.251465 0.409424 0.54541 0.620117 0.645996 0.657715
[perf] iters=5, avg=1.2738 ms, min=1.231 ms, max=1.36 ms
Fuser inference completed successfully!
```

### `test_head`

Purpose: run the detection head only with a dumped fused feature tensor.

Usage:

```bash
./test_head [warmup] [iters] [head_model] [input_bin] [--fp32]
```

Example command:

```bash
./test_head 1 5
```

Expected output includes:

```text
Saved 81920 floats to head_outputs/score.bin
Saved 32768 floats to head_outputs/rot.bin
Sample score values (first 10): -10.2188 -15.1719 -12.3906 -10.5 -10.3047 -10.8828 -10.1797 -9.50781 -9.00781 -8.375
[perf] iters=5, avg=8.58259 ms, min=4.77576 ms, max=14.5848 ms
```

## Choosing The Right Binary

- Use `bevfusion` for the decoupled split-model end-to-end application.
- Use `bevfusion_unified` for the unified end-to-end application.
- Use the `test_*` binaries when isolating one subsystem or validating an intermediate artifact path.