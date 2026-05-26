# BEVFusion Getting Started Guide

## Overview

This repo is the **training + ONNX-conversion** side for the deploy pipelines in
[applications.iot.video-edge-cloud.gpu-bev-fusion/deploy](../deploy).
Two parallel deploy pipelines are supported; pick the one matching your deploy target:

| Pipeline | Deploy binary | Lidar encoder | ONNX artifacts | Custom ops (and where they live) | Deploy directories |
|---|---|---|---|---|---|
| **A — PointPillars-based** (§4) | `./bevfusion` | PillarFeatureNet + PointPillarsScatter | **4 independent ONNX**: `camera.backbone` / `lidar_pfe` / `fuser` / `head` | `bevpoolv2` + `pillarscatter` + voxelizer + post-processing: hand-written **SYCL** kernels (single-use ops) | `deploy/src/pointpillars/`, `deploy/src/pointpillars/voxelizer.cpp` |
| **B — Second-based** (§5) | `./bevfusion_unified` | SparseEncoder (SparseConv3d + SubMConv3d) | **Single unified ONNX**: `bevfusion_unified.onnx` | `SparseConvolution` + `SubMConv3d` are called many times and fused with BN/ReLU, so they (and `BevPoolV2` / `SparseToDense`) live inside the **OpenVINO GPU plugin** | `deploy/src/bevfusion_unified/`, `deploy/src/bevfusion_unified/voxelizer_sycl.cpp` |

**Dataset coverage**

| Pipeline | V2X-I (DAIR-V2X-I) | KITTI |
|---|---|---|
| A — PointPillars (`./bevfusion`)         | ✅ (§4.3) | ✅ (§4.4) |
| B — Second (`./bevfusion_unified`)       | ✅ (§5.3) | ✅ (§5.4) |

Both pipelines use the same `--preset v2x|kitti` switch in deploy. Reference user commands (V2X-I is the default preset):

```bash
# Pipeline B — unified (default INT8 XML; pass --fp16 for the FP16 ONNX)
./bevfusion_unified <REPO>/training/data/dair-v2x-i-kitti/training --num-samples 1000
./bevfusion_unified <REPO>/training/data/kitti-v2x/training --num-samples 1000 --preset kitti

# Pipeline A — split 4-ONNX (default FP32; pass --int8 for the 4-XML INT8 path)
./bevfusion <REPO>/training/data/dair-v2x-i-kitti/training --num-samples 1000 --int8
./bevfusion <REPO>/training/data/kitti-v2x/training --num-samples 1000 --int8 --preset kitti
```

> **Already have NVIDIA's CUDA-V2XFusion checkpoint?** If you only want to deploy
> NVIDIA's reference `dense_epoch_100_.pth` (or your own CUDA-V2XFusion-trained
> ckpt) on Intel GPU — no retraining, no in-repo training-side work — skip this
> guide and follow [Guide/nvidia_ckpt_to_intel_gpu.md](Guide/nvidia_ckpt_to_intel_gpu.md).
> It's a focused weight-conversion path: NVIDIA `.pth` → 4 ONNX + INT8 IR → drop
> into `deploy/data/v2xfusion/pointpillars/`. Pipeline A + V2X-I only.

Sections:
1. Environment setup (shared)
2. Dataset preparation (V2X-I, KITTI)
3. Shared reference — custom ONNX ops, config inheritance
4. Pipeline A: PointPillars-based BEVFusion (`./bevfusion`)
5. Pipeline B: Second-based BEVFusion (`./bevfusion_unified`)

---

## 1. Environment Setup

Throughout this document the following placeholders are used; substitute them
with paths appropriate to your machine:

| Placeholder | Meaning |
|---|---|
| `<REPO>` | Absolute path to this repository's root (the parent of `training/` and `deploy/`) |
| `<BEV_ENV>` | Python virtual env for training + ONNX export + Pipeline A INT8 quantization (see §1.1) |
| `<SPCONV_ENV>` | Python virtual env for Pipeline B INT8 quantization + standalone OV inference (see §1.2) |
| `<OPENVINO_ROOT>` | Custom-built OpenVINO root containing `bin/intel64/Release/` (see §1.2) |
| `<TORCHPACK>` | Launcher prefix for `tools/train.py` / `tools/test.py`. See §1.1 for two options. |

Two Python environments, kept strictly separate:

### 1.1 `bevEnv` — training + ONNX export + Pipeline A INT8 quantization

```bash
PYTHON=<BEV_ENV>/bin/python
PIP=<BEV_ENV>/bin/pip

# Build CUDA extensions (including bev_pool_v2)
cd <REPO>/training
$PIP install -e .

# Verify bev_pool_v2 extension
$PYTHON -c "from mmdet3d.ops.bev_pool_v2.bev_pool import bev_pool_v2, OVBEVPoolv2; print('OK')"
```

Pipeline A (PointPillars split 4-ONNX, §4) INT8 quantization via `export/pointpillars/quantize_all.py` runs in `bevEnv`.

**Launching `tools/train.py` / `tools/test.py`** — both scripts use
`torchpack.distributed`. There are two launch modes:

```bash
# Option A — single-process, no torch.distributed (recommended for single GPU).
#   Pass --no-dist to train.py / test.py so they skip dist.init() and the
#   mmcv MMDistributedDataParallel wrapper (incompatible with newer PyTorch).
TORCHPACK="<BEV_ENV>/bin/python"
# usage:
#   $TORCHPACK tools/train.py --no-dist <config> --run-dir ...
#   $TORCHPACK tools/test.py  --no-dist <config> <ckpt> --eval bbox

# Option B — multi-GPU distributed via torchpack dist-run (needs OpenMPI:
#   `apt install openmpi-bin`). torchpack's default mpirun flags are OpenMPI
#   syntax and will fail under Intel MPI. Drop --no-dist when using this.
TORCHPACK="<BEV_ENV>/bin/torchpack dist-run -np <NGPU> <BEV_ENV>/bin/python"
```

All `$TORCHPACK tools/train.py --no-dist ...` commands shown below default to
Option A (single-GPU). For multi-GPU, switch to Option B's `TORCHPACK` and
remove `--no-dist`.

### 1.2 `spconvEnv` — standalone OV inference + Pipeline B INT8 quantization

```bash
OV_DIR=<OPENVINO_ROOT>/bin/intel64/Release
export PYTHONPATH="$OV_DIR/python:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$OV_DIR:${LD_LIBRARY_PATH:-}"
OV_PYTHON=<SPCONV_ENV>/bin/python
```

The OpenVINO build above must include the opset15 registration patch for
`BevPoolV2 / SparseConvolution / SparseToDense`. Without this patch Pipeline B's
saved INT8 IR cannot be read back.

`spconvEnv` is used for:
- Pipeline B unified quantization (`export/quantize_unified.py`, NNCF 3.1 + custom OV, §5.2.6).
- Standalone OpenVINO-side inference tests (`tools/bevfusion_standalone_ov_inference.py`, §5.3).

It is **not** used for Pipeline A (`export/pointpillars/quantize_all.py`) — that stays in `bevEnv`.

Intel Arc **B580** is the reference GPU (exposed as `GPU.1`).

---

## 2. Dataset Preparation

Both pipelines read from `<REPO>/training/data/`. Two datasets are supported:

| Dataset | Source | Final on-disk layout under `data/` |
|---|---|---|
| DAIR-V2X-I | [DAIR-V2X-I Google Drive bundle](https://drive.google.com/drive/folders/1FlBbtJfuoEOc0ey9wkkU1lGr5JtS4-gc) (`single-infrastructure-side-image/`, `single-infrastructure-side-velodyne/`, `single-infrastructure-side-label/`, `data_info.json`) | `data/dair-v2x-i/` (native) **+** `data/dair-v2x-i-kitti/` (KITTI-format mirror used by the evaluator) |
| KITTI | [KITTI 3D Object](https://www.cvlibs.net/datasets/kitti/eval_object.php?obj_benchmark=3d) raw download (`training/{image_2,velodyne,calib,label_2}`, `testing/{image_2,velodyne,calib}`, `ImageSets/{train,val}.txt`) | `data/kitti-v2x/` (V2X-format mirror produced by `tools/convert_kitti_to_v2x_format.py`) |

Configs reference these paths through `dataset_root` / `dataset_kitti_root`
(`configs/V2X-I/default.yaml:2-3`, `configs/Kitti/default.yaml:2-3`); if you put
the data anywhere else, override those two keys instead of changing the configs.

### 2.1 DAIR-V2X-I

Download the DAIR-V2X-I bundle from
[this Google Drive folder](https://drive.google.com/drive/folders/1FlBbtJfuoEOc0ey9wkkU1lGr5JtS4-gc),
then follow BEVHeight's data preparation document end-to-end for the
KITTI-format conversion and pkl generation steps:
[ADLab-AutoDrive/BEVHeight — docs/prepare_dataset.md](https://github.com/ADLab-AutoDrive/BEVHeight/blob/main/docs/prepare_dataset.md).
That guide produces the `dair_12hz_infos_{train,val}.pkl` annotation files
this repo loads.

**Final layout** (this is what `data/dair-v2x-i/` and `data/dair-v2x-i-kitti/`
should look like after BEVHeight's prep is done):

```
data/
├── dair-v2x-i/                         # native DAIR-V2X-I
│   ├── velodyne/                       # *.pcd / *.bin point clouds
│   ├── image/                          # *.jpg camera frames
│   ├── calib/                          # virtuallidar↔camera + camera intrinsics JSONs
│   ├── label/                          # native JSON labels
│   ├── data_info.json                  # DAIR-V2X-I sample manifest
│   ├── dair_12hz_infos_train.pkl       # produced by BEVHeight prep
│   └── dair_12hz_infos_val.pkl         # produced by BEVHeight prep
└── dair-v2x-i-kitti/                   # KITTI-format mirror (evaluator uses this)
    ├── training/
    │   ├── calib/                      # KITTI-style calib *.txt
    │   ├── image_2/                    # KITTI-style images
    │   ├── label_2/                    # KITTI-style labels (referenced as dataset_kitti_root)
    │   └── velodyne/                   # KITTI-style point clouds
    ├── testing/                        # placeholder (empty — DAIR-V2X-I single-side has no public test split)
    └── ImageSets/
        ├── train.txt
        ├── val.txt
        ├── trainval.txt
        └── test.txt                    # placeholder, paired with empty testing/
```

Sanity check after prep:

```bash
ls data/dair-v2x-i/dair_12hz_infos_{train,val}.pkl   # both must exist
ls data/dair-v2x-i-kitti/training/label_2 | head -3  # KITTI-style label txts
```

### 2.2 KITTI

KITTI prep is a two-stage flow: standard MMDetection3D infos generation, then
`tools/convert_kitti_to_v2x_format.py` to produce a V2XDataset-compatible
mirror.

#### 2.2.1 Stage 1 — generate `kitti_infos_*.pkl` with MMDetection3D v1.x

This repo's `tools/create_data.py` only handles nuScenes; the `kitti_infos_*.pkl`
files come from **upstream MMDetection3D v1.x** (`tools/create_data.py kitti`).
After downloading the KITTI 3D Object archive into `<KITTI_RAW>/` with the
standard layout:

```
<KITTI_RAW>/
├── ImageSets/{train,val,trainval,test}.txt
├── training/{calib,image_2,label_2,velodyne}/
└── testing/{calib,image_2,velodyne}/
```

run upstream MMDetection3D v1.x's KITTI converter (in any clone of
[open-mmlab/mmdetection3d](https://github.com/open-mmlab/mmdetection3d) at a
v1.x tag — the converter is independent of this repo):

```bash
# in an mmdet3d v1.x checkout
python tools/create_data.py kitti \
    --root-path ./data/kitti \
    --out-dir ./data/kitti \
    --extra-tag kitti \
    --with-plane
```

`--with-plane` consumes the `planes/` road-plane txts that ship with KITTI 3D
Object and bakes per-frame ground-plane info into `kitti_infos_*.pkl` — needed
if your downstream training uses ground-plane augmentation. Drop the flag if
your `<KITTI_RAW>/training/` does not contain `planes/`.

Substitute `./data/kitti` with `<KITTI_RAW>` (an absolute path or a path
relative to the mmdet3d checkout).

You should end up with the layout the user-side mmdet3d run produces (matches
what's already on the reference machine):

```
<KITTI_RAW>/
├── gt_database/
├── kitti_dbinfos_train.pkl
├── kitti_gt_database/
├── kitti_infos_test.pkl
├── kitti_infos_train.pkl
├── kitti_infos_trainval.pkl
├── kitti_infos_val.pkl
├── testing/
└── training/
```

The `kitti_infos_{train,val,trainval,test}.pkl` files are the ones consumed by
Stage 2. `gt_database/` and `kitti_dbinfos_train.pkl` are not needed for
training in this repo.

#### 2.2.2 Stage 2 — convert to V2XDataset format

Use this repo's converter to build the V2X-format mirror under
`data/kitti-v2x/`:

```bash
cd <REPO>/training
$PYTHON tools/convert_kitti_to_v2x_format.py \
    --src-root <KITTI_RAW> \
    --dst-root data/kitti-v2x
```

The script (see [tools/convert_kitti_to_v2x_format.py](tools/convert_kitti_to_v2x_format.py)):

1. Symlinks `training/{image_2,velodyne,label_2,calib}` and top-level
   `image/`, `velodyne/` from `<KITTI_RAW>` into `data/kitti-v2x/`.
2. Generates `data/kitti-v2x/calib/virtuallidar_to_camera/<frame>.json`
   from each KITTI `calib/<frame>.txt` (computes `lidar2cam = R0_rect @ Tr_velo_to_cam`).
3. Rewrites each `kitti_infos_<split>.pkl` from MMDetection3D v1.x's
   `{metainfo, data_list}` schema into the flat list-of-dict V2XDataset
   schema (KITTI cam-rect bbox → lidar-frame center + nuScenes Box convention
   `(w, l, h)` + yaw_lidar; KITTI category → nuScenes category).

**Final layout:**

```
data/
└── kitti-v2x/
    ├── image/                          → <KITTI_RAW>/training/image_2 (symlink)
    ├── velodyne/                       → <KITTI_RAW>/training/velodyne (symlink)
    ├── calib/
    │   └── virtuallidar_to_camera/
    │       ├── 000000.json
    │       ├── 000001.json
    │       └── ...
    ├── training/
    │   ├── image_2/                    → <KITTI_RAW>/training/image_2 (symlink)
    │   ├── velodyne/                   → <KITTI_RAW>/training/velodyne (symlink)
    │   ├── label_2/                    → <KITTI_RAW>/training/label_2 (symlink)
    │   └── calib/                      → <KITTI_RAW>/training/calib (symlink)
    ├── testing/
    │   ├── image_2/                    → <KITTI_RAW>/testing/image_2 (symlink)
    │   ├── velodyne/                   → <KITTI_RAW>/testing/velodyne (symlink)
    │   └── calib/                      → <KITTI_RAW>/testing/calib (symlink)
    ├── kitti_infos_train.pkl           # converted from <KITTI_RAW>/kitti_infos_train.pkl
    ├── kitti_infos_val.pkl
    ├── kitti_infos_trainval.pkl        # only if Stage 1 produced it
    └── kitti_infos_test.pkl            # only if Stage 1 produced it
```

Sanity check:

```bash
ls data/kitti-v2x/kitti_infos_{train,val}.pkl
ls data/kitti-v2x/calib/virtuallidar_to_camera | wc -l    # should match #frames
ls data/kitti-v2x/training/label_2 | head -3
```

`configs/Kitti/default.yaml` already points `dataset_root: data/kitti-v2x` and
`dataset_kitti_root: data/kitti-v2x/training/label_2`, so no config edits are
required if you placed the output here.

---

## 3. Shared Reference

### 3.1 Custom ONNX Operators

All custom ops are registered under domain `org.openvinotoolkit`:

| Operator | Used by | Where implemented | Description |
|---|---|---|---|
| `BevPoolV2` | Pipeline B ONNX (camera branch) | OpenVINO GPU plugin | Camera-to-BEV view transform using precomputed geometry |
| `SparseConvolution` | Pipeline B ONNX (lidar encoder) | OpenVINO GPU plugin | 3D sparse convolution with fused BN + optional ReLU |
| `SparseToDense` | Pipeline B ONNX (lidar encoder) | OpenVINO GPU plugin | Sparse feature map → dense BEV tensor |

Pipeline A has **no custom ops inside ONNX** — `bevpoolv2` / `pillarscatter` /
voxelization / post-processing are all SYCL kernels outside the ONNX graph, so
standard OpenVINO can load all 4 PP ONNXs unmodified.

### 3.2 Config Inheritance

All configs follow a fixed recursive-override chain. Two encoder families live under distinct
top-level neck directories (`lssfpn` for PointPillars, `secfpn` for Second):

```
configs/default.yaml
  └─ configs/<DATASET>/default.yaml                      # dataset, image_size, object_classes
       └─ configs/<DATASET>/det/default.yaml             # detection model type (BEVFusion)
            └─ configs/<DATASET>/det/centerhead/default.yaml
                 ├─ .../lssfpn/default.yaml              # ← Pipeline A (PointPillars)
                 │    └─ .../camera+pointpillar/default.yaml
                 │         └─ .../resnet34/default.yaml
                 └─ .../secfpn/default.yaml              # ← Pipeline B (Second)
                      └─ .../camera+lidar/default.yaml
                           └─ .../resnet34/default.yaml   # (+ optional bevpoolv2.yaml)
```

`<DATASET>` ∈ `V2X-I`, `Kitti`, `nuscenes`. Backbone variants under each leaf
directory: `resnet34`, `resnet50`, `fasternet`.

---

## 4. Pipeline A — PointPillars-based BEVFusion (4 ONNX)

### 4.1 Design

Four independent ONNX files, each an independently quantizable / replaceable deploy stage:

| Stage | ONNX file | Content | I/O |
|---|---|---|---|
| camera    | `camera.backbone.onnx` | ResNet34 → GeneralizedLSSFPN → DepthNet | `img [1,1,3,864,1536]` → `camera_feature`, `camera_depth_weights` |
| lidar PFE | `lidar_pfe.onnx` / `lidar_pfe_v7000.onnx` | PillarFeatureNet (f_cluster / f_center / mask fused into the graph) | `features [V,100,4]`, `num_voxels [V]`, `coors [V,4]` → `pillar_features [V,64]` |
| fuser     | `fuser.onnx` | ConvFuser + decoder.backbone + decoder.neck | `cam_bev [1,80,128,128]`, `lidar_bev [1,64,128,128]` → `middle [1,256,128,128]` |
| head      | `head.onnx` | CenterHead (shared_conv + task_heads, no decoder) | `middle [1,256,128,128]` → 12 task tensors |

**Stays outside ONNX** (SYCL kernels in deploy):
- Voxelization — [deploy/src/pointpillars/voxelizer.cpp](../deploy/src/pointpillars/voxelizer.cpp)
- `bevpoolv2` (camera BEV pooling) — deploy SYCL kernel
- `PointPillarsScatter` (PFE output → dense BEV canvas) — deploy SYCL kernel
- CenterHead post-processing (heatmap top-k, box decode, rotate-NMS) — deploy SYCL kernel

The voxelizer's `coors` layout is `(batch_idx, x_idx, y_idx, z_idx)` — **opposite** to
Pipeline B's voxelizer layout `(batch, z, y, x)`. The deploy-side SYCL voxelizers
must follow each pipeline's own layout; the two cannot be shared.

### 4.2 Generic Workflow

Throughout §4.2 we use placeholder variables; §4.3 / §4.4 fill them in per dataset:

```bash
PP_CONFIG=<path to a camera+pointpillar/resnet34/default.yaml>
PP_CKPT=<path to the trained pth>
```

#### 4.2.1 Training

```bash
$TORCHPACK tools/train.py --no-dist $PP_CONFIG --mode dense --run-dir ./work_dirs/<dataset>/pp/
```

The BEVFusion base model in [mmdet3d/models/fusion_models/bevfusion.py](mmdet3d/models/fusion_models/bevfusion.py) auto-selects hard-voxelize (PointPillars) vs DynamicScatter (Second) based on `max_num_points > 0` — no training-code changes are needed to switch encoders.

#### 4.2.2 Inference & Visualization

```bash
$PYTHON tools/inference_vis.py $PP_CONFIG $PP_CKPT \
    --split train --mode pred --bbox-score 0.3 --out-dir viz_pp
```

| Argument | Description | Default |
|---|---|---|
| `--mode` | `gt` or `pred` | `gt` |
| `--split` | `train` or `val` | `val` |
| `--bbox-score` | score threshold | `None` |
| `--out-dir` | output directory | `viz` |

Outputs go to `<out-dir>/camera/*.png` and `<out-dir>/lidar/*.png`. The script is
encoder-agnostic — any model that emits `boxes_3d / scores_3d / labels_3d` works.

#### 4.2.3 ONNX Export — All 4 Files in One Call

```bash
$PYTHON export/pointpillars/export_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT \
    --out-dir export/onnx/pointpillars
```

Reference output sizes (V2X-I):

| File | Size | Nodes | Notes |
|---|---|---|---|
| `camera.backbone.onnx` | 88 MB | 113 | ResNet34 + LSSFPN + DepthNet |
| `lidar_pfe.onnx` | 17 KB | 198 | dynamic V (up to 12000) |
| `fuser.onnx` | 405 KB | 51 | ConvFuser + decoder.backbone + decoder.neck → `middle[1,256,128,128]` |
| `head.onnx` | 52 MB | 38 | CenterHead only, consumes `middle` |

Individual exports (if you only want one stage):

```bash
$PYTHON export/pointpillars/export-camera.py --config $PP_CONFIG --ckpt $PP_CKPT -o export/onnx/pointpillars/camera.backbone.onnx
$PYTHON export/pointpillars/export-lidar.py  --config $PP_CONFIG --ckpt $PP_CKPT -o export/onnx/pointpillars/lidar_pfe.onnx
$PYTHON export/pointpillars/export-fuser.py  --config $PP_CONFIG --ckpt $PP_CKPT -o export/onnx/pointpillars/fuser.onnx
$PYTHON export/pointpillars/export-head.py   --config $PP_CONFIG --ckpt $PP_CKPT -o export/onnx/pointpillars/head.onnx
```

#### 4.2.4 Static-V PFE Export (recommended for deploy)

Dynamic V (number of non-empty pillars) forces OpenVINO to re-specialize the PFE kernel every frame. A fixed V bakes a single shape and drops PFE latency.

```bash
# V=7000 — recommended static-V setting for deploy --int8
$PYTHON export/pointpillars/export-lidar.py \
    --config $PP_CONFIG --ckpt $PP_CKPT \
    --fixed-v 7000 --split val \
    -o export/onnx/pointpillars/lidar_pfe_v7000.onnx
```

The exporter pads trace inputs to `V=N`, and deploy auto-detects static shape.

Choose V based on your dataset statistics with enough margin. Recommended default is `V=7000`.

#### 4.2.5 INT8 Quantization — All 4 ONNXs in One Call

Produces `quantized_camera.xml` / `quantized_lidar_pfe.xml` / `quantized_fuser.xml` / `quantized_head.xml` via NNCF PTQ on 300 calibration frames.

```bash
$PYTHON export/pointpillars/quantize_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx-dir export/onnx/pointpillars \
    --out-dir  export/onnx/pointpillars \
    --num-samples 300
```

`quantize_all.py` prefers `lidar_pfe_v7000.onnx` when both static and dynamic PFE ONNX are present.

Individual stages (all share the same CLI shape):

```bash
$PYTHON export/pointpillars/quantize_camera_backbone.py --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx export/onnx/pointpillars/camera.backbone.onnx \
    --out  export/onnx/pointpillars/quantized_camera.xml --num-samples 300
$PYTHON export/pointpillars/quantize_lidar_pfe.py --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx export/onnx/pointpillars/lidar_pfe_v7000.onnx \
    --out  export/onnx/pointpillars/quantized_lidar_pfe.xml --num-samples 300
$PYTHON export/pointpillars/quantize_fuser.py --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx export/onnx/pointpillars/fuser.onnx \
    --out  export/onnx/pointpillars/quantized_fuser.xml --num-samples 300
$PYTHON export/pointpillars/quantize_head.py --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx export/onnx/pointpillars/head.onnx \
    --out  export/onnx/pointpillars/quantized_head.xml --num-samples 300
```

**fuser/head split** — `fuser.onnx` contains decoder backbone+neck, and `head.onnx` contains CenterHead shared conv + task heads.


#### 4.2.6 End-to-End Command Sequence

```bash
cd <REPO>/training

# 1) Train
$TORCHPACK tools/train.py --no-dist $PP_CONFIG --mode dense --run-dir ./work_dirs/<dataset>/pp/

# 2) Inference sanity check
$PYTHON tools/inference_vis.py $PP_CONFIG $PP_CKPT --split train --mode pred

# 3) Export 4 ONNX files
$PYTHON export/pointpillars/export_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT --out-dir export/onnx/pointpillars

# 4) Static-V PFE for deploy INT8 (V=7000 matches deploy's max_voxels)
$PYTHON export/pointpillars/export-lidar.py \
    --config $PP_CONFIG --ckpt $PP_CKPT --fixed-v 7000 --split val \
    -o export/onnx/pointpillars/lidar_pfe_v7000.onnx

# 5) INT8 quantization (all 4 stages) — auto picks lidar_pfe_v7000.onnx
$PYTHON export/pointpillars/quantize_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx-dir export/onnx/pointpillars --out-dir export/onnx/pointpillars \
    --num-samples 300
```

#### 4.2.7 Deploy Repo Runtime (`./bevfusion`)

The deploy-side split-pipeline runner is `./bevfusion` in the sibling repo
`<REPO>`.
It loads the 4 split models from `deploy/data/<preset_dir>/pointpillars/`:

```
camera.backbone.onnx  / quantized_camera.xml
lidar_pfe.onnx        / lidar_pfe_v7000.onnx / quantized_lidar_pfe.xml
fuser.onnx            / quantized_fuser.xml
head.onnx             / quantized_head.xml
```

Copy the artifacts from `export/onnx/pointpillars/` to
`deploy/data/<preset_dir>/pointpillars/` before running — the deploy repo does
not read from the training tree. `<preset_dir>` is `v2xfusion` for DAIR-V2X-I
and `kitti` for KITTI (see [deploy/src/pipeline/dataset_preset.cpp](../deploy/src/pipeline/dataset_preset.cpp) for the full preset geometry table). The `--preset` flag passed to the binary is `v2x` or `kitti`.

```bash
cd <REPO>/deploy/build

# FP32 (loads the 4 .onnx files; PFE prefers v7000 when present, else dynamic).
# Preset defaults to v2x when --preset is omitted.
./bevfusion <DATASET_PATH> --num-samples 30 --vis                                # V2X-I FP32
./bevfusion <DATASET_PATH> --preset kitti --num-samples 30 --vis                 # KITTI  FP32

# INT8 (loads the 4 quantized_*.xml files; PFE pinned to V=7000)
./bevfusion <DATASET_PATH> --num-samples 30 --vis --int8                         # V2X-I INT8
./bevfusion <DATASET_PATH> --preset kitti --num-samples 30 --vis --int8          # KITTI  INT8

# Per-stage INT8 toggles
./bevfusion ... --int8-camera --int8-pfe --int8-fuser --int8-head
```

Flags:
- `--preset v2x` / `--preset kitti` selects both geometry (image size, BEV grid, pc_range, out_size_factor) and the model dir.
- `--int8` turns on INT8 for all 4 stages; individual toggles let you mix.
- `--dump-pred --pred-dir DIR` writes KITTI-format box txts for offline metric eval.
- `--vis` writes `bevfusion.mp4` into the build dir.

### 4.3 Dataset: V2X-I (DAIR-V2X-I)

```bash
PP_CONFIG=configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml
PP_CKPT=work_dirs/V2X-I/pp/latest.pth
PP_ONNX_DIR=export/onnx/pointpillars
DEPLOY_DIR=<REPO>/deploy/data/v2xfusion/pointpillars
```

For deploy consistency, use static-V with `--fixed-v 7000` in the PFE export step.

**End-to-end commands:**

```bash
cd <REPO>/training

# 1) Train
$TORCHPACK tools/train.py --no-dist $PP_CONFIG --mode dense --run-dir ./work_dirs/V2X-I/pp

# 2) Inference sanity check
$PYTHON tools/inference_vis.py $PP_CONFIG $PP_CKPT --split val --mode pred

# 3) Export 4 ONNX
$PYTHON export/pointpillars/export_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT --out-dir $PP_ONNX_DIR

# 4) Static-V PFE for INT8 deploy
$PYTHON export/pointpillars/export-lidar.py \
    --config $PP_CONFIG --ckpt $PP_CKPT --fixed-v 7000 --split val \
    -o $PP_ONNX_DIR/lidar_pfe_v7000.onnx

# 5) INT8 quantization (auto picks v7000)
$PYTHON export/pointpillars/quantize_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx-dir $PP_ONNX_DIR --out-dir $PP_ONNX_DIR --num-samples 300

# 6) Publish to deploy
cp $PP_ONNX_DIR/{camera.backbone,fuser,head,lidar_pfe,lidar_pfe_v7000}.onnx "$DEPLOY_DIR/"
cp $PP_ONNX_DIR/quantized_{camera,lidar_pfe,fuser,head}.{xml,bin} "$DEPLOY_DIR/"

# 7) Deploy runtime (V2X-I — preset defaults to v2x; FP32 omits --int8)
cd <REPO>/deploy/build
./bevfusion <REPO>/training/data/dair-v2x-i-kitti/training --num-samples 1000           # FP32
./bevfusion <REPO>/training/data/dair-v2x-i-kitti/training --num-samples 1000 --int8    # INT8
```

### 4.4 Dataset: KITTI

```bash
PP_CONFIG=configs/Kitti/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml
PP_CKPT=work_dirs/Kitti/pp/latest.pth
PP_ONNX_DIR=export/onnx/pointpillars/kitti
DEPLOY_DIR=<REPO>/deploy/data/kitti/pointpillars
```

Backbone variants under `configs/Kitti/det/centerhead/lssfpn/camera+pointpillar/`:
`{default,resnet34,resnet50,fasternet}/`. Dataset-scoped ONNX output dir
(`export/onnx/pointpillars/kitti/`) keeps KITTI artifacts from colliding with V2X-I's.

Geometry differences vs V2X-I (from `deploy/src/pipeline/dataset_preset.cpp`):

| | KITTI | V2X-I |
|---|---|---|
| image (W×H) | 1280×384 | 1536×864 |
| camera feat (W×H) | 80×24 | 96×54 |
| BEV grid | 100×100 | 128×128 |
| pc_range | [0,-40,-5]→[80,40,3] | [0,-51.2,-5]→[102.4,51.2,3] |
| post_center_range | [0,-45,-5]→[85,45,3] | same as pc_range |
| split_post_voxel_size | 0.1 | 0.2 |
| out_size_factor | 8 | 4 |


**KITTI-specific note:**

- Always pass `--config` and `--ckpt` explicitly to quantization/export scripts.

**End-to-end commands:**

```bash
cd <REPO>/training

# 1) Train
$TORCHPACK tools/train.py --no-dist $PP_CONFIG --mode dense --run-dir ./work_dirs/Kitti/pp

# 2) Inference sanity check
$PYTHON tools/inference_vis.py $PP_CONFIG $PP_CKPT --split val --mode pred

# 3) Export 4 ONNX
$PYTHON export/pointpillars/export_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT --out-dir $PP_ONNX_DIR

# 4) Static-V PFE for INT8 deploy (V=7000)
$PYTHON export/pointpillars/export-lidar.py \
    --config $PP_CONFIG --ckpt $PP_CKPT --fixed-v 7000 --split val \
    -o $PP_ONNX_DIR/lidar_pfe_v7000.onnx

# 5) INT8 quantization (all 4 stages; quantize_all auto picks v7000)
$PYTHON export/pointpillars/quantize_all.py \
    --config $PP_CONFIG --ckpt $PP_CKPT \
    --onnx-dir $PP_ONNX_DIR --out-dir $PP_ONNX_DIR --num-samples 300

# 6) Publish to deploy
cp $PP_ONNX_DIR/{camera.backbone,fuser,head,lidar_pfe,lidar_pfe_v7000}.onnx "$DEPLOY_DIR/"
cp $PP_ONNX_DIR/quantized_{camera,lidar_pfe,fuser,head}.{xml,bin} "$DEPLOY_DIR/"

# 7) Deploy runtime (KITTI — pass --preset kitti; FP32 omits --int8)
cd <REPO>/deploy/build
./bevfusion <REPO>/training/data/kitti-v2x/training \
    --num-samples 1000 --preset kitti              # FP32
./bevfusion <REPO>/training/data/kitti-v2x/training \
    --num-samples 1000 --int8 --preset kitti       # INT8
```

Validation target: KITTI INT8 frame-by-frame box counts match FP32 exactly on the smoke set.

---

## 5. Pipeline B — Second-based BEVFusion (unified ONNX)

### 5.1 Design

A **single** `bevfusion_unified.onnx` merges camera + lidar + fuser + head. Unlike Pipeline A, the lidar sparse encoder contains ~21 `SparseConv3d` / `SubMConv3d` layers that:

- are called many times, with BN and ReLU fused into each sparse-conv op;
- require custom forward implementations that don't map cleanly to ONNX standard ops.

These ops (plus `BevPoolV2` for camera and `SparseToDense` at the encoder boundary) therefore live as **OpenVINO GPU plugin custom ops** (§2.1) rather than as SYCL kernels outside the graph. Deploy runs one OpenVINO infer call per frame and the plugin dispatches sparse kernels internally.

Deploy directories:
- [deploy/src/bevfusion_unified/](../deploy/src/bevfusion_unified/) — pipeline driver + SYCL voxelizer (`voxelizer_sycl.cpp` lives here, `coors` = `(batch, z, y, x)`)
- [deploy/test/bevfusion_unified.cpp](../deploy/test/bevfusion_unified.cpp) — `./bevfusion_unified` entry point

### 5.2 Generic Workflow

Placeholder variables used throughout §5.2; §5.3–§5.4 fill them per dataset:

```bash
CP_CONFIG=<path to a camera+lidar/resnet34/{default,bevpoolv2}.yaml>
CP_CKPT=<path to the trained pth, e.g. work_dirs/<dataset>/bevpoolv2/latest.pth>
```

#### 5.2.1 Training — BEVPool V1 vs V2

**BEVPool V1 (default):**

```bash
CUDA_VISIBLE_DEVICES=0 $TORCHPACK tools/train.py --no-dist \
    configs/<DATASET>/det/centerhead/secfpn/camera+lidar/resnet34/default.yaml \
    --run-dir ./work_dirs/<dataset>/bevpoolv1
```

**BEVPool V2 (recommended for deploy):** add `use_bevpool: bevpoolv2` under `vtransform`. Either create a sibling `bevpoolv2.yaml`:

```yaml
model:
  encoders:
    camera:
      vtransform:
        use_bevpool: bevpoolv2
        depth_threshold: 0
```

or inline the override in the existing `resnet34/default.yaml`. Then:

```bash
CUDA_VISIBLE_DEVICES=0 $TORCHPACK tools/train.py --no-dist \
    configs/<DATASET>/det/centerhead/secfpn/camera+lidar/resnet34/bevpoolv2.yaml \
    --run-dir ./work_dirs/<dataset>/bevpoolv2
```

**work_dirs convention**: KITTI uses dataset-scoped subdirs
(`work_dirs/Kitti/bevpoolv2/`). For V2X-I the same convention is
`work_dirs/V2X-I/bevpoolv2/`.

#### 5.2.2 Inference & Visualization

```bash
$PYTHON tools/inference_vis.py $CP_CONFIG $CP_CKPT \
    --mode pred --out-dir viz --bbox-score 0.3
```

| Argument | Description | Default |
|---|---|---|
| `--mode` | `gt` or `pred` | `gt` |
| `--split` | `train` or `val` | `val` |
| `--bbox-score` | min confidence | `None` |
| `--bbox-classes` | filter by class indices | `None` |
| `--out-dir` | output directory | `viz` |

Outputs: `<out-dir>/{camera,lidar,map}/`.

#### 5.2.3 Precompute BEVPool V2 Geometry

**Run this before any ONNX export** — generates `indices.bin` + `intervals.bin` consumed by both the unified model and the camera sub-model:

```bash
# From a saved tensor data sample
$PYTHON export/precompute_geometry.py $CP_CONFIG $CP_CKPT \
    --data-path tools/dump/00000/example-data.pth \
    -o export/geometry

# Or from the dataset directly
$PYTHON export/precompute_geometry.py $CP_CONFIG $CP_CKPT \
    --from-dataset --split val --sample-idx 0 \
    -o export/geometry
```

Output (bev_latest compatible):

| File | Format | Description |
|---|---|---|
| `indices.bin` | `[uint32 count][count * uint32]` | 466560 sorted point indices (full grid, sentinel included) |
| `intervals.bin` | `[uint32 count][count * int3(start, end, bev_rank)]` | intervals with absolute offsets; sentinel has rank=-1 |
| `geometry.pth` | PyTorch tensor dict | same data, PyTorch-native |

#### 5.2.4 Export Unified ONNX

Exports the full BEVFusion pipeline as a single ONNX (internally merges 3 sub-models):

```bash
$PYTHON export/export_unified_onnx.py $CP_CONFIG $CP_CKPT \
    --geometry-dir export/geometry \
    -o export/onnx/bevfusion_unified.onnx
```

Unified model I/O:

| Input | Shape | Description |
|---|---|---|
| `img` | `[1, 3, 864, 1536]` | camera image (NCHW) |
| `indices` | `[num_points]` | BEVPoolV2 sorted indices (from geometry) |
| `intervals` | `[num_intervals, 3]` | BEVPoolV2 intervals (start, end, bev_rank) |
| `voxel_features` | `[N_vox, 4]` | voxelized lidar features |
| `voxel_indices` | `[N_vox, 4]` | voxel coordinates (batch, z, y, x) |

> Older unified exports may still use 5-D `img` (`[1, 1, 3, H, W]`) — both are supported by the standalone inference script.

| Output | Shape | Description |
|---|---|---|
| `task{i}_heatmap` | `[1, 5, 128, 128]` | per-task class heatmap |
| `task{i}_reg` | `[1, 2, 128, 128]` | regression offset |
| `task{i}_height` | `[1, 1, 128, 128]` | height |
| `task{i}_dim` | `[1, 3, 128, 128]` | box dimensions (l, w, h) |
| `task{i}_rot` | `[1, 2, 128, 128]` | rotation (sin, cos) |
| `task{i}_vel` | `[1, 2, 128, 128]` | velocity (vx, vy) |

#### 5.2.5 OpenVINO Inference — Unified Model

Runs the unified ONNX with CenterHead post-processing and visualization. Requires Intel Arc GPU for `SparseConvolution` ops.

**From dataset** ([tools/bevfusion_standalone_ov_inference.py](tools/bevfusion_standalone_ov_inference.py)) — no mmdet3d runtime dependency:

```bash
$OV_PYTHON tools/bevfusion_standalone_ov_inference.py \
    --data-root <data/...> --ann-file <...infos_val.pkl> \
    --onnx-path <bevfusion_unified[_dataset].onnx> \
    --geometry-dir <export/geometry[_dataset]> \
    --device GPU.1 --out-dir viz_standalone \
    --bbox-score 0.3 --max-samples 10
```

Per-dataset argument values live in §5.3–§5.4.

- Auto-adapts `img` rank for both 4-D NCHW (`[1,3,H,W]`) and legacy 5-D (`[1,1,3,H,W]`) unified ONNX formats.
- **Geometry auto-detection**: `init_dataset_geometry_from_onnx()` reads `pc_range` / `voxel_size` / `sparse_shape` from ONNX attributes at startup, so the same script works across datasets without manual source edits.


| Argument | Description | Default |
|---|---|---|
| `--onnx-path` | unified ONNX | (required) |
| `--geometry-dir` | `indices.bin` + `intervals.bin` | (required) |
| `--device` | OpenVINO device (`GPU.1` for Arc B580) | `CPU` |
| `--bbox-score` | score threshold | `0.1` |
| `--max-samples` | frames to process | `None` |

#### 5.2.6 INT8 Quantization — Unified Model

Produces `bevfusion_unified_int8.xml`/`.bin` from the FP32 unified ONNX via NNCF PTQ.

**Prerequisites:**

- Custom OpenVINO build with the opset15 patch (§1.2) — without it the saved IR can't be read back.
- Two envs, no mixing: `bevEnv` for the offline voxelizer dump; `spconvEnv` (py3.12 + custom OV + NNCF 3.1) for the actual quantization.
- `$CP_CKPT` + matching `bevpoolv2.yaml` — the bevpoolv1 and bevpoolv2 checkpoints are **not** interchangeable.
- `export/geometry/indices.bin` + `intervals.bin` (§5.2.3).
- `export/onnx/bevfusion_unified.onnx` (§5.2.4).
- `export/dump_voxels.py` now reads directly from `cfg.data.<split>` (no dependency on `tools/dump/*/example-data.pth`).

One-time NNCF install:

```bash
<SPCONV_ENV>/bin/pip install "nncf==3.1.0"
```

**Three-stage pipeline:**

```bash
cd <REPO>/training

# Stage 1 — voxelizer dump (bevEnv, needs mmdet3d/spconv)
$PYTHON export/dump_voxels.py $CP_CONFIG $CP_CKPT \
    -o export/calib_voxels --num-frames 400 --split val

# Stage 2 — pseudo-GT from FP32 self-distillation (spconvEnv)
#   Quantization validation is self-distilled: FP32 decoded boxes are used as pseudo-GT.
rm -f export/calib_voxels/_pseudo_gt.npz
$OV_PYTHON -u export/quantize_unified.py \
    --stage pseudo-gt --n-calib 300 --n-val 100 \
    --model-fp32 export/onnx/bevfusion_unified.onnx \
    --geo-dir export/geometry \
    --calib-dir export/calib_voxels \
    --pseudo-gt-cache export/calib_voxels/_pseudo_gt.npz

# Stage 3 — NNCF PTQ (spconvEnv)
#   Default output: <REPO>/deploy/data/v2xfusion/onnx/bevfusion_unified_int8.xml/.bin
$OV_PYTHON -u export/quantize_unified.py \
    --stage quantize --n-calib 300 --n-val 100 --plain-ptq \
    --preset mixed --activation-range histogram \
    --model-fp32 export/onnx/bevfusion_unified.onnx \
    --geo-dir export/geometry \
    --calib-dir export/calib_voxels \
    --pseudo-gt-cache export/calib_voxels/_pseudo_gt.npz
```

**Recommended flags:**

| Flag | Value | Reason |
|---|---|---|
| `--preset` | `mixed` | Recommended default preset. |
| `--activation-range` | `histogram` | Recommended default activation range. |
| `--plain-ptq` | — | Use plain PTQ mode. |
| `--n-calib` / `--n-val` | 300 / 100 | Default. |

FP-only custom ops are handled automatically by `quantize_unified.py`.

**Outputs:**

| File | Notes |
|---|---|
| `bevfusion_unified.onnx` | FP32 source |
| `bevfusion_unified_int8.xml` | INT8 IR topology |
| `bevfusion_unified_int8.bin` | INT8 weights |

Use the default `--activation-range histogram` unless you have validated alternatives on your target deployment.

#### 5.2.7 End-to-End Command Sequence

For release workflows, use the dataset-specific end-to-end command blocks in §5.3 (V2X-I) and §5.4 (KITTI).

### 5.3 Dataset: V2X-I (DAIR-V2X-I)

```bash
CP_CONFIG=configs/V2X-I/det/centerhead/secfpn/camera+lidar/resnet34/bevpoolv2.yaml
CP_CKPT=work_dirs/V2X-I/bevpoolv2/latest.pth
GEO_DIR=export/geometry
CALIB_DIR=export/calib_voxels
UNIFIED_ONNX=export/onnx/bevfusion_unified.onnx
DEPLOY_V2X_DIR=<REPO>/deploy/data/v2xfusion/second
```

Deploy artifacts are stored in `deploy/data/v2xfusion/second/`:
`bevfusion_unified_fp16.onnx` and `bevfusion_unified_int8.xml`/`.bin`.

**End-to-end commands:**

```bash
cd <REPO>/training

# 1) Train (BEVPoolV2 recommended, see §5.2.1)
$TORCHPACK tools/train.py --no-dist $CP_CONFIG --run-dir ./work_dirs/V2X-I/bevpoolv2

# 2) Validate
$PYTHON tools/inference_vis.py $CP_CONFIG $CP_CKPT --split val --mode pred

# 3) Precompute BEVPoolV2 geometry
$PYTHON export/precompute_geometry.py $CP_CONFIG $CP_CKPT \
    --from-dataset --split val --sample-idx 0 -o $GEO_DIR

# 4) Export unified ONNX
$PYTHON export/export_unified_onnx.py $CP_CONFIG $CP_CKPT \
    --geometry-dir $GEO_DIR -o $UNIFIED_ONNX

# 5) Calibration voxel dump (dataset-driven)
$PYTHON export/dump_voxels.py $CP_CONFIG $CP_CKPT \
    -o $CALIB_DIR --num-frames 400 --split val

# 6) INT8 quantize (3-stage, see §5.2.6)
rm -f $CALIB_DIR/_pseudo_gt.npz
$OV_PYTHON -u export/quantize_unified.py --stage pseudo-gt \
    --n-calib 300 --n-val 100 \
    --model-fp32 $UNIFIED_ONNX --geo-dir $GEO_DIR \
    --calib-dir $CALIB_DIR --pseudo-gt-cache $CALIB_DIR/_pseudo_gt.npz
$OV_PYTHON -u export/quantize_unified.py --stage quantize \
    --n-calib 300 --n-val 100 --plain-ptq \
    --preset mixed --activation-range histogram \
    --model-fp32 $UNIFIED_ONNX --geo-dir $GEO_DIR \
    --calib-dir $CALIB_DIR --pseudo-gt-cache $CALIB_DIR/_pseudo_gt.npz \
    --output $DEPLOY_V2X_DIR/bevfusion_unified_int8.xml

# 7) Publish deploy artifacts (FP16 ONNX is exported with --fp16 from
#    export/export_unified_onnx.py; INT8 .xml/.bin are produced by step 6)
cp export/onnx/bevfusion_unified_fp16.onnx     $DEPLOY_V2X_DIR/
# (the INT8 IR was already written into $DEPLOY_V2X_DIR by --output above)

# 8) Deploy runtime — preset defaults to v2x; INT8 is the default model
cd <REPO>/deploy/build
LD_LIBRARY_PATH=<OPENVINO_ROOT>/bin/intel64/Release:${LD_LIBRARY_PATH:-} \
./bevfusion_unified <REPO>/training/data/dair-v2x-i-kitti/training \
    --num-samples 1000                                              # INT8 (default)

LD_LIBRARY_PATH=<OPENVINO_ROOT>/bin/intel64/Release:${LD_LIBRARY_PATH:-} \
./bevfusion_unified <REPO>/training/data/dair-v2x-i-kitti/training \
    --num-samples 1000 --fp16                                       # FP16
```

Standalone OV inference (`tools/bevfusion_standalone_ov_inference.py`) is useful for Python-side debugging without rebuilding the deploy binary; it defaults `--ann-file` to `<data-root>/dair_12hz_infos_val.pkl`:

```bash
$OV_PYTHON tools/bevfusion_standalone_ov_inference.py \
    --data-root data/dair-v2x-i \
    --onnx-path $UNIFIED_ONNX --geometry-dir $GEO_DIR \
    --device GPU.1 --out-dir viz_standalone \
    --bbox-score 0.3 --max-samples 10
```

### 5.4 Dataset: KITTI

```bash
CP_CONFIG=configs/Kitti/det/centerhead/secfpn/camera+lidar/resnet34/bevpoolv2.yaml
CP_CKPT=work_dirs/Kitti/bevpoolv2/latest.pth
GEO_DIR=export/geometry_kitti
CALIB_DIR=export/calib_voxels_kitti
UNIFIED_ONNX=export/bevfusion_unified_kitti.onnx
DEPLOY_KITTI_DIR=<REPO>/deploy/data/kitti/second
```

Per-dataset paths (`export/geometry_kitti`, `export/calib_voxels_kitti`, etc.) keep KITTI artifacts from overwriting V2X-I's. The deploy KITTI second-based dir holds the same two model variants as V2X-I:
`bevfusion_unified_fp16.onnx` + `bevfusion_unified_int8.xml`/`.bin`. The unified pipeline auto-detects `pc_range` / `voxel_size` from the ONNX; the only deploy-side switch needed is `--preset kitti`.

For KITTI quantization, always pass `--config $CP_CONFIG` to `quantize_unified.py`.

**End-to-end commands:**

```bash
cd <REPO>/training

# 1) Train
$TORCHPACK tools/train.py --no-dist $CP_CONFIG --run-dir ./work_dirs/Kitti/bevpoolv2

# 2) Validate
$PYTHON tools/inference_vis.py $CP_CONFIG $CP_CKPT --split val --mode pred

# 3) Precompute BEVPoolV2 geometry (KITTI-specific dir)
$PYTHON export/precompute_geometry.py $CP_CONFIG $CP_CKPT \
    --from-dataset --split val --sample-idx 0 -o $GEO_DIR

# 4) Export unified ONNX (KITTI-specific name)
$PYTHON export/export_unified_onnx.py $CP_CONFIG $CP_CKPT \
    --geometry-dir $GEO_DIR -o $UNIFIED_ONNX

# 5) Calibration voxel dump
$PYTHON export/dump_voxels.py $CP_CONFIG $CP_CKPT \
    -o $CALIB_DIR --num-frames 400 --split val

# 6) INT8 quantize (KITTI MUST pass --config; see note above)
rm -f $CALIB_DIR/_pseudo_gt.npz
$OV_PYTHON -u export/quantize_unified.py --stage pseudo-gt \
    --config $CP_CONFIG \
    --n-calib 300 --n-val 100 \
    --model-fp32 $UNIFIED_ONNX --geo-dir $GEO_DIR \
    --calib-dir $CALIB_DIR --pseudo-gt-cache $CALIB_DIR/_pseudo_gt.npz
$OV_PYTHON -u export/quantize_unified.py --stage quantize \
    --config $CP_CONFIG \
    --n-calib 300 --n-val 100 --plain-ptq \
    --preset mixed --activation-range histogram \
    --model-fp32 $UNIFIED_ONNX --geo-dir $GEO_DIR \
    --calib-dir $CALIB_DIR --pseudo-gt-cache $CALIB_DIR/_pseudo_gt.npz \
    --output $DEPLOY_KITTI_DIR/bevfusion_unified_int8.xml

# 7) Publish FP16 source to deploy
cp export/onnx/bevfusion_unified_kitti_fp16.onnx \
    $DEPLOY_KITTI_DIR/bevfusion_unified_fp16.onnx

# 8) Deploy runtime — pass --preset kitti; INT8 is the default model
cd <REPO>/deploy/build
LD_LIBRARY_PATH=<OPENVINO_ROOT>/bin/intel64/Release:${LD_LIBRARY_PATH:-} \
./bevfusion_unified <REPO>/training/data/kitti-v2x/training \
    --num-samples 1000 --preset kitti                                # INT8 (default)

LD_LIBRARY_PATH=<OPENVINO_ROOT>/bin/intel64/Release:${LD_LIBRARY_PATH:-} \
./bevfusion_unified <REPO>/training/data/kitti-v2x/training \
    --num-samples 1000 --preset kitti --fp16                         # FP16
```

The `.bin` sibling file is auto-produced beside the `.xml`. Standalone Python-side inference for offline debugging:

```bash
OV_ROOT=<OPENVINO_ROOT>/bin/intel64/Release \
PYTHONPATH=$OV_ROOT/python:$PYTHONPATH \
LD_LIBRARY_PATH=$OV_ROOT:$LD_LIBRARY_PATH \
<SPCONV_ENV>/bin/python tools/bevfusion_standalone_ov_inference.py \
    --data-root data/kitti-v2x \
    --ann-file data/kitti-v2x/kitti_infos_val.pkl \
    --onnx-path $UNIFIED_ONNX --geometry-dir $GEO_DIR \
    --device GPU.1 --out-dir viz_standalone \
    --bbox-score 0.5 --max-samples 100
```

> For the **split** (PP) pipeline on KITTI — which is what `./bevfusion --preset kitti --int8` runs — see §4.4. The two paths are independent: `./bevfusion` ≠ `./bevfusion_unified`.


