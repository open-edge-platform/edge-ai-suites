# KITTI-360 Conversion Guide

The commands below assume this project root is already the current working directory.

## Overview

This guide explains how to convert KITTI-360 into the KITTI-style input layout expected by the deploy-side tooling.

The converter rewrites camera images, calibration files, and LiDAR point clouds into a KITTI-like directory tree that can be consumed by workflows that accept a KITTI-style dataset root.

Current behavior to be aware of:

- Images are written to `image_2/` as encoded `.bin` files.
- Calibration files are written to `calib/`.
- LiDAR point clouds are copied to `velodyne/` as `.bin` files.
- A reduced-FOV copy is also generated under `velodyne_reduced/`.
- The converter does not create `label_2/`. If you need evaluation or label-aware workflows, you must prepare labels separately.

## Prerequisites

Before starting, ensure you have the following:

- **KITTI-360 dataset**: download it from the [KITTI-360 website](http://www.cvlibs.net/datasets/kitti-360/).
- **Python 3 environment** with the converter dependencies installed.
- **Required libraries**:
  - `numpy`
  - `opencv-python`
  - `mmcv`
  - `mmengine`
  - `mmdet3d` following the official installation guide: https://mmdetection3d.readthedocs.io/en/latest/get_started.html

The input dataset layout is expected to look like this:

```text
KITTI-360/
  calibration/
  data_2d_raw/
  data_2d_semantics/
  data_3d_bboxes/
  data_3d_raw/
  data_poses/
```

## Quick Start

Convert the default set of supported drives:

```bash
python3 tools/how_to_generate_kitti_format_dataset/kitti360_convert_to_kitti.py \
  /path/to/KITTI-360 \
  /path/to/output_kitti360
```

By default, the script tries to convert drive IDs `0 2 3 4 5 6 7 8 9 10 18`. Missing drives are skipped with a message instead of aborting the whole run.

To convert only a subset of drives, pass `--drive-ids` explicitly:

```bash
python3 tools/how_to_generate_kitti_format_dataset/kitti360_convert_to_kitti.py \
  /path/to/KITTI-360 \
  /path/to/output_kitti360 \
  --drive-ids 0 2 3
```

## Output Layout

The converter creates the following directories under the output root:

```text
<output_kitti360>/
  calib/
  image_2/
  velodyne/
  velodyne_reduced/
```

Notes:

- `image_2/` contains encoded image `.bin` files rather than `.png` or `.jpg` files.
- `velodyne_reduced/` contains field-of-view filtered point clouds generated after the main conversion step.
- No `label_2/` directory is produced by this script.

## Verification

After conversion, perform a quick structural check:

```bash
find /path/to/output_kitti360 -maxdepth 1 -type d | sort
find /path/to/output_kitti360/image_2 -type f | head
find /path/to/output_kitti360/calib -type f | head
find /path/to/output_kitti360/velodyne -type f | head
```

If you need to use the converted dataset with deploy-side inference commands, treat the output directory as a KITTI-style dataset root and follow the applicable runtime flow in `../../docs/GSG.md` or `../../docs/Testing.md`.

If you need evaluation with `tools/README_eval.md`, add or generate a matching `label_2/` directory first.
