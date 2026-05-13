# Deployment Documentation

This deploy tree contains the Intel GPU inference assets for the BEVFusion project. It packages the native C++/SYCL executables, Docker workflow, custom OpenVINO integration, smoke-test automation, sample assets, and dataset conversion or evaluation tools needed to validate the deployment stack end to end.

## Pipelines

- `bevfusion`: split-model pipeline with decoupled PointPillars-style lidar preprocessing plus camera BEV, fusion, and detection heads.
- `bevfusion_unified`: unified pipeline that runs a single BEVFusion-style network with custom OpenVINO ops.

## Project Contents

- `build.sh`, `install_*.sh`, `autotest*.sh`: build, dependency-install, and smoke-test entry points.
- `docker/`: container build and runtime helpers.
- `docs/`: host setup, getting-started, and executable reference guides.
- `tools/`: evaluation helpers and dataset conversion scripts.
- `data/`: bundled sample datasets, models, and intermediate dump bins used by validation flows.

## Documentation Map

Choose the workflow that matches your goal:

1. `docker/README_Docker.md`

   Recommended first stop for a quick run with the published Docker image.

2. `docs/Prerequisites.md`

   Prepare the host for a native build and install the project dependencies.

3. `docs/GSG.md`

   Build and run the native applications, export predictions, and troubleshoot common issues.

4. `docs/Testing.md`

   Review the available executables plus the native and Docker smoke-test flows.

5. `tools/README_eval.md`

   Run KITTI-format evaluation and interpret the generated metrics.

6. `tools/how_to_generate_kitti_format_dataset/v2x_pandaset_guide.md`

   Convert PandaSet or DAIR-V2X-I into KITTI format with the bundled helper scripts.

7. `tools/how_to_generate_kitti_format_dataset/kitti360_guide.md`

   Convert Kitti360 into KITTI format with the bundled helper scripts.

## Recommended Quick Start

Pull the published image and run the container smoke test:

```bash
docker pull intel/tfcc:bevfusion
bash autotest_docker.sh --image intel/tfcc:bevfusion
```

The published image keeps the `intel/tfcc:bevfusion` name after pull. If you want the shorter local tag used by some helper defaults, add it yourself:

```bash
docker tag intel/tfcc:bevfusion tfcc:bevfusion
```

To work interactively inside the published image instead:

```bash
bash docker/run_docker.sh intel/tfcc:bevfusion
```

If this container workflow is enough for your use case, you can skip the native build steps in `docs/Prerequisites.md` and `docs/GSG.md`.

## Native Host Entry Points

```bash
bash install_driver_related_libs.sh
bash install_project_related_libs.sh
bash build.sh
```

## Runtime Environment

For a native host build, or from an interactive shell inside the container, use:

```bash
source /opt/intel/oneapi/setvars.sh
source /opt/intel/openvino/setupvars.sh
```

## Automated Test Runner

For a containerized smoke test of a published or prebuilt image, use:

```bash
bash autotest_docker.sh --image intel/tfcc:bevfusion
```

If you retagged the published image to `tfcc:bevfusion`, or built a local image with that tag, you can omit `--image`.

To copy a host dataset into the container for the run, pass:

```bash
bash autotest_docker.sh --image intel/tfcc:bevfusion --dataset-path /path/to/kitti_dataset
```

To run the native host binaries in one shot and get pass/fail counts plus the final performance lines for `bevfusion` and `bevfusion_unified`, use:

```bash
bash autotest.sh
```

This command uses the bundled sample dataset at `data/v2xfusion/dataset`, builds a one-frame mini dataset for smoke tests, and keeps the default quiet status-only console output.
Each test case has a default 120-second timeout so a stuck binary is reported as a failed case instead of blocking the whole run. Use `--case-timeout SEC` to adjust it, or `--case-timeout 0` to disable the timeout.
When `data/model_asset_mode.txt` says `mode=dummy`, `autotest.sh` switches to runtime smoke mode and validates only the `bevfusion` and `bevfusion_unified` applications. The current release bundle uses dummy weights, so this smoke mode is the expected default.

To run against your own KITTI-style dataset instead, pass `--dataset-path`:

```bash
bash autotest.sh --dataset-path /path/to/kitti_dataset
```

In explicit dataset mode, `bevfusion` and `bevfusion_unified` run on the provided dataset path and ignore the repeat controls. Use `--verbose` if you want each binary's live stdout/stderr on the console.

If you want to build the Docker image locally instead of pulling it, add `--build-image --custom-openvino-install-dir /path/to/custom_openvino/install` to `autotest_docker.sh`.

## Included Sample Assets

- `data/v2xfusion/dataset/`: DAIR-V2X sample dataset for smoke tests.
- `data/v2xfusion/pointpillars/`: DAIR-V2X split-model assets for `bevfusion`, including INT8 IR and FP32 ONNX files.
- `data/v2xfusion/second/`: DAIR-V2X unified-model assets for `bevfusion_unified`, including INT8 IR and FP16 ONNX files.
- `data/kitti/dataset/`: KITTI-360 sample dataset for smoke tests.
- `data/kitti/pointpillars/`: KITTI-360 split-model assets for `bevfusion`, including INT8 IR and FP32 ONNX files.
- `data/kitti/second/`: KITTI-360 unified-model assets for `bevfusion_unified`, including INT8 IR and FP16 ONNX files.
- `data/v2xfusion/dump_bins/`: intermediate tensors used by several module tests.

The bundled model files under `data/*/pointpillars` and `data/*/second` are dummy weights in the current release package. They preserve the runtime interfaces so the pipelines can be launched and profiled, but they do not produce meaningful detections or evaluation results.

For split-model PFE selection, both DAIR-V2X and KITTI-360 prefer the v7000 PFE shape and fall back to v6000 only when v7000 is not present. Default split and unified runs request INT8 models; on Battlemage GPUs the split pipeline keeps the known INT8 fuser protection and uses `fuser.onnx` while the other available INT8 split components remain enabled. `--fp32` selects split-model FP32 ONNX components, and `--fp16` selects unified FP16 ONNX models.

## Additional Utilities

- `tools/kitti_3d_eval.py`: KITTI-format evaluation helper.
- `tools/README_eval.md`: evaluation workflow and result interpretation.
- `tools/how_to_generate_kitti_format_dataset/v2x_pandaset_guide.md`: PandaSet and DAIR-V2X-I conversion guide plus verification helpers.
- `tools/how_to_generate_kitti_format_dataset/kitti360_guide.md`: KITTI-360 conversion guide.