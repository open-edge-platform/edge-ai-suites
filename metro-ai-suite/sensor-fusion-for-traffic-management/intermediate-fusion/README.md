# BEVFusion Intel GPU Deployment

This project provides Intel GPU deployment assets for two BEVFusion pipelines.

## Pipelines

- `bevfusion`: split-model PointPillars pipeline.
- `bevfusion_unified`: unified SECOND pipeline that runs a single ONNX model with custom OpenVINO ops.

Both pipelines use the runtime environment installed under `/opt/intel/openvino`.

## Documentation

- `deploy/README.md`: deployment documentation index.
- `deploy/docker/README_Docker.md`: recommended Docker-first validation and local image workflows.
- `deploy/docs/Prerequisites.md`: native host preparation and installation steps.
- `deploy/docs/GSG.md`: build, run, evaluate, and troubleshoot the native deployment flow.
- `deploy/docs/Testing.md`: executable reference and native/container smoke-test workflows.
- `deploy/tools/README_eval.md`: KITTI evaluation workflow and metric reference.
- `deploy/tools/how_to_generate_kitti_format_dataset/dair_v2x_guide.md`: DAIR-V2X-I conversion workflow and calibration verification helpers.
- `deploy/tools/how_to_generate_kitti_format_dataset/kitti360_guide.md`: KITTI-360 conversion workflow.

Start with `deploy/README.md`, then follow the linked guides from inside that subproject directory.

## Dataset Layout

The applications expect a KITTI-style dataset layout:

```text
<dataset_root>/
  calib/
  image_2/
  label_2/
  velodyne/
```

Supported file types:

- Images: `.jpg`, `.jpeg`, `.png`, and encoded `.bin`
- Point clouds: `.bin` and `.pcd`
- Calibration: `.txt`
- Labels: `.txt`

## Repository Layout

```text
deploy/install_driver_related_libs.sh    Install GPU, NPU, and monitoring dependencies
deploy/install_project_related_libs.sh   Install build dependencies and custom OpenVINO
deploy/install_custom_openvino.sh        Build and install custom OpenVINO
deploy/build.sh                   Configure and build the deployment binaries
deploy/docs/                      Deployment guides and references
deploy/test/                      Main applications and module tests
deploy/data/v2xfusion/            Example models, sample data, and dump bins
deploy/docker/                    Docker build and runtime assets
deploy/tools/                     Evaluation, conversion, and utility scripts
training/                         Training-side utilities and export tools
```

## Start Here

Start with `deploy/README.md` for the documentation hub. Use `deploy/docker/README_Docker.md` for the quickest validation path. Use `deploy/docs/Prerequisites.md` and `deploy/docs/GSG.md` when you need the full native build workflow.