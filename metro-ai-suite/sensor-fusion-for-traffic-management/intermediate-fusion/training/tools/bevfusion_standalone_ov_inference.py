#!/usr/bin/env python3
"""
BEVFusion standalone inference via OpenVINO — NO mmdet3d dependency.

This script loads the unified bevfusion_unified.onnx and runs end-to-end
inference using only: numpy, opencv, matplotlib, Pillow, openvino.
It can be copied to any machine (e.g. Intel GPU) without mmdet3d installed.

Pipeline:
  1. Load & preprocess image (resize, crop, normalize)
  2. Load & voxelize point cloud (pure-numpy hard voxelization)
  3. Load precomputed BEVPool V2 geometry (indices.bin, intervals.bin)
  4. Run unified ONNX model via OpenVINO
  5. Decode CenterHead outputs (top-K, coordinate transform, NMS)
  6. Visualize results (camera image + lidar BEV)

Usage (common env prefix):
  OV_DIR=/home/jie/workspace/openvino/bin/intel64/Release
  export PYTHONPATH="$OV_DIR/python:$PYTHONPATH"
  export LD_LIBRARY_PATH="$OV_DIR:$LD_LIBRARY_PATH"
  PY=/home/jie/env/spconvEnv/bin/python

  # KITTI
  $PY tools/bevfusion_standalone_ov_inference.py \
      --data-root data/kitti-v2x \
      --ann-file data/kitti-v2x/kitti_infos_val.pkl \
      --onnx-path export/bevfusion_unified_kitti.onnx \
      --geometry-dir export/geometry_kitti \
      --device GPU.1 \
      --out-dir viz_standalone \
      --bbox-score 0.5 \
      --max-samples 100

  # V2X-I (DAIR-V2X-I)
  $PY tools/bevfusion_standalone_ov_inference.py \
      --data-root data/dair-v2x-i \
      --ann-file data/dair-v2x-i/dair_12hz_infos_val.pkl \
      --onnx-path export/onnx/bevfusion_unified.onnx \
      --geometry-dir export/geometry \
      --device GPU.1 \
      --out-dir viz_standalone_v2x \
      --bbox-score 0.3 \
      --max-samples 10

Note: pc_range / voxel_size / sparse_shape are auto-read from the ONNX's
BevPoolV2 + SparseConvolution attrs at startup by
`init_dataset_geometry_from_onnx()`. Do NOT hand-edit the module-level
constants to switch datasets — mixing a V2X-range scale with a KITTI-exported
ONNX produces ghost detections.
"""

import argparse
import copy
import json
import os
import pickle
import struct
import sys
from importlib import import_module
from typing import Dict, List, Optional, Tuple

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openvino as ov
from PIL import Image

# ---------------------------------------------------------------------------
# Constants — auto-detected from the ONNX at startup.
#
# These MUST match the config the ONNX was exported from. Using the wrong
# values (e.g. V2X range 102.4×102.4 on a KITTI-exported ONNX with baked
# spatial_shape=800×800) causes voxel coords to exceed the SparseConv grid
# and produces ghost detections.
#
# The values below are defaults; `init_dataset_geometry_from_onnx(path)` at
# startup overrides them from the ONNX's BevPoolV2 / SparseConvolution attrs
# so the same script works for KITTI / V2X-I / nuScenes without manual edits.
POINT_CLOUD_RANGE = [0, -40.0, -5, 80.0, 40.0, 3]
VOXEL_SIZE = [0.1, 0.1, 0.2]
SPARSE_SHAPE = [800, 800, 40]
MAX_NUM_POINTS = 10
MAX_VOXELS_TEST = 160000


_ALLOWED_PICKLE_GLOBALS = {
    "builtins": {
        "dict", "list", "tuple", "set", "frozenset", "slice",
        "str", "int", "float", "bool", "bytes",
    },
    "collections": {"OrderedDict", "defaultdict"},
    "numpy": {"dtype", "ndarray"},
    "numpy.core.multiarray": {"_reconstruct", "scalar"},
    "numpy._core.multiarray": {"_reconstruct", "scalar"},
}


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed_names = _ALLOWED_PICKLE_GLOBALS.get(module)
        if allowed_names and name in allowed_names:
            return getattr(import_module(module), name)
        raise pickle.UnpicklingError(f"Unsupported pickle global: {module}.{name}")


def load_restricted_pickle(file_obj):
    return RestrictedUnpickler(file_obj).load()


def init_dataset_geometry_from_onnx(onnx_path: str) -> None:
    """Read pc_range / voxel_size / spatial_shape from the ONNX attrs.

    Source of truth inside the unified ONNX:
        - BevPoolV2 attrs: x_bound_min/max/step, y_bound_min/max/step,
                           z_bound_min/max/step, d_bound_min/max
        - First SparseConvolution attr: input_spatial_shape [H, W, D]

    Fills module globals POINT_CLOUD_RANGE, VOXEL_SIZE, SPARSE_SHAPE.
    """
    global POINT_CLOUD_RANGE, VOXEL_SIZE, SPARSE_SHAPE
    import onnx

    m = onnx.load(onnx_path, load_external_data=False)
    bevpool = next((n for n in m.graph.node if n.op_type == "BevPoolV2"), None)
    spconv = next((n for n in m.graph.node if n.op_type == "SparseConvolution"), None)
    if bevpool is None or spconv is None:
        print(f"  [auto-geometry] WARNING: could not find BevPoolV2 / SparseConvolution "
              f"in {onnx_path}; keeping defaults {POINT_CLOUD_RANGE}, {SPARSE_SHAPE}")
        return

    def fget(node, name, default=None):
        for a in node.attribute:
            if a.name == name:
                return a.f
        return default

    def ints(node, name):
        for a in node.attribute:
            if a.name == name:
                return list(a.ints)
        return None

    xb_min = fget(bevpool, "x_bound_min")
    xb_max = fget(bevpool, "x_bound_max")
    xb_step = fget(bevpool, "x_bound_step")
    yb_min = fget(bevpool, "y_bound_min")
    yb_max = fget(bevpool, "y_bound_max")
    zb_min = fget(bevpool, "z_bound_min")
    zb_max = fget(bevpool, "z_bound_max")
    sp_shape = ints(spconv, "input_spatial_shape")  # [H, W, D]

    # pc_range uses [x_min, y_min, z_min, x_max, y_max, z_max]
    POINT_CLOUD_RANGE = [xb_min, yb_min, zb_min, xb_max, yb_max, zb_max]
    # BevPoolV2 x/y step is at BEV-feature resolution (OUT_SIZE_FACTOR × voxel_size)
    # Recover voxel_size from spatial_shape and pc_range
    H, W, D = sp_shape  # [H, W, D] voxel grid
    vx = (xb_max - xb_min) / W
    vy = (yb_max - yb_min) / H
    vz = (zb_max - zb_min) / D
    VOXEL_SIZE = [vx, vy, vz]
    SPARSE_SHAPE = [H, W, D]
    print(f"  [auto-geometry] pc_range={POINT_CLOUD_RANGE}")
    print(f"  [auto-geometry] voxel_size={VOXEL_SIZE}")
    print(f"  [auto-geometry] sparse_shape={SPARSE_SHAPE}")

# Image preprocessing
# ORIG_H/W is read per-frame from the image file (datasets like KITTI have
# multiple native resolutions). FINAL_H/W is read from the compiled ONNX's
# `img` input shape so it automatically matches the training config's
# `image_size` (864x1536 for V2X-I, 384x1280 for KITTI, etc.).
IMG_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
IMG_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)
FINAL_H = None  # set from compiled_model in main()
FINAL_W = None

# CenterHead config
OUT_SIZE_FACTOR = 8
BBOX_CODE_SIZE = 9
MAX_NUM_DETECTIONS = 500
SCORE_THRESHOLD = 0.001
POST_CENTER_RANGE = np.array([0.0, -61.2, -10.0, 122.4, 61.2, 10.0])

# 2-task head configuration
TASKS = [
    ["car", "truck", "construction_vehicle", "bus", "trailer"],       # task 0: 5 classes
    ["barrier", "motorcycle", "bicycle", "pedestrian", "traffic_cone"],  # task 1: 5 classes
]

OBJECT_CLASSES = [
    "car", "truck", "construction_vehicle", "bus", "trailer",
    "barrier", "motorcycle", "bicycle", "pedestrian", "traffic_cone",
]

# NMS config (per 6-head legacy, but we have 2 tasks)
# For 2-task: task0 uses circle NMS, task1 uses rotate NMS
NMS_TYPE = ["circle", "rotate"]
NMS_THR = 0.2
PRE_MAX_SIZE = 1000
POST_MAX_SIZE = 83
MIN_RADIUS = [4, 12, 10, 1, 0.85, 0.175]  # per-class radius for circle NMS

OBJECT_PALETTE = {
    "car": (255, 158, 0),
    "truck": (255, 99, 71),
    "construction_vehicle": (233, 150, 70),
    "bus": (255, 69, 0),
    "trailer": (255, 140, 0),
    "barrier": (112, 128, 144),
    "motorcycle": (255, 61, 99),
    "bicycle": (220, 20, 60),
    "pedestrian": (0, 0, 230),
    "traffic_cone": (47, 79, 79),
}


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="BEVFusion standalone OV inference")
    p.add_argument("--data-root", type=str, default="data/dair-v2x-i")
    p.add_argument("--ann-file", type=str, default=None,
                   help="Pickle annotation file. Default: <data-root>/dair_12hz_infos_val.pkl")
    p.add_argument("--onnx-path", type=str, default="export/bevfusion_unified.onnx")
    p.add_argument("--geometry-dir", type=str, default="export/geometry")
    p.add_argument("--device", type=str, default="GPU", help="OpenVINO device (CPU, GPU)")
    p.add_argument("--out-dir", type=str, default="viz_standalone")
    p.add_argument("--bbox-score", type=float, default=None)
    p.add_argument("--max-samples", type=int, default=None)
    p.add_argument("--split", type=str, default="val", choices=["train", "val"])
    return p.parse_args()


# ---------------------------------------------------------------------------
# 1. Data loading
# ---------------------------------------------------------------------------

def load_annotations(ann_file: str) -> list:
    """Load annotation pickle file."""
    with open(ann_file, "rb") as f:
        data = load_restricted_pickle(f)
    return data


def load_pointcloud(file_path: str) -> np.ndarray:
    """Load point cloud file (.bin or .pcd), return NxC float32 array."""
    if file_path.endswith(".bin"):
        points = np.fromfile(file_path, dtype=np.float32).reshape(-1, 4)
        return points
    return _load_pcd(file_path)


def _load_pcd(file_path: str) -> np.ndarray:
    """Load PCD file, return Nx4 float32 array (x, y, z, intensity)."""
    pcd_type_map = {
        ("F", 4): np.float32,
        ("F", 8): np.float64,
        ("U", 1): np.uint8,
        ("U", 2): np.uint16,
        ("U", 4): np.uint32,
        ("I", 2): np.int16,
        ("I", 4): np.int32,
    }
    meta = {}
    with open(file_path, "rb") as f:
        while True:
            line = f.readline().strip().decode("utf-8")
            if line.startswith("# .PCD"):
                continue
            if line.startswith("VERSION"):
                meta["version"] = line[8:]
            elif line.startswith("FIELDS"):
                meta["fields"] = line[7:].split()
            elif line.startswith("SIZE"):
                meta["size"] = list(map(int, line[5:].split()))
            elif line.startswith("TYPE"):
                meta["type"] = line[5:].split()
            elif line.startswith("COUNT"):
                meta["count"] = list(map(int, line[6:].split()))
            elif line.startswith("WIDTH"):
                meta["width"] = int(line[6:])
            elif line.startswith("HEIGHT"):
                meta["height"] = int(line[7:])
            elif line.startswith("VIEWPOINT"):
                pass
            elif line.startswith("POINTS"):
                meta["points"] = int(line[7:])
            elif line.startswith("DATA"):
                meta["data_type"] = line[5:]
                break

        dtype_list = list(zip(
            meta["fields"],
            [pcd_type_map[(t, s)] for t, s in zip(meta["type"], meta["size"])],
        ))
        dtype = np.dtype(dtype_list)

        if meta["data_type"] == "ascii":
            data = np.loadtxt(f, dtype=dtype, delimiter=" ")
        elif meta["data_type"] == "binary":
            buf = f.read(meta["points"] * dtype.itemsize)
            data = np.frombuffer(buf, dtype=dtype)
        elif meta["data_type"] == "binary_compressed":
            import lzf
            csz, usz = struct.unpack("II", f.read(8))
            buf = lzf.decompress(f.read(csz), usz)
            data_out = np.zeros(meta["width"], dtype=dtype)
            ix = 0
            for dti in range(len(dtype)):
                dt = dtype[dti]
                nbytes = dt.itemsize * meta["width"]
                data_out[dtype.names[dti]] = np.frombuffer(buf[ix:ix + nbytes], dt)
                ix += nbytes
            data = data_out
        else:
            raise ValueError(f"Unknown PCD data type: {meta['data_type']}")

    # Convert structured array to float32
    out = np.zeros((len(data), len(dtype)), dtype=np.float32)
    for i, name in enumerate(dtype.names):
        out[:, i] = data[name]
    return out


def load_lidar2camera(data_root: str, lidar_file: str) -> np.ndarray:
    """Load lidar-to-camera calibration from JSON, return 4x4 matrix."""
    calib_file = lidar_file.replace("velodyne", "calib/virtuallidar_to_camera")
    calib_file = os.path.splitext(calib_file)[0] + ".json"
    calib_path = os.path.join(data_root, calib_file)
    with open(calib_path, "r") as f:
        calib = json.load(f)
    R = np.array(calib["rotation"], dtype=np.float64)
    t = np.array(calib["translation"], dtype=np.float64).flatten()
    mat = np.eye(4, dtype=np.float64)
    mat[:3, :3] = R
    mat[:3, 3] = t
    return mat


# ---------------------------------------------------------------------------
# 2. Image preprocessing
# ---------------------------------------------------------------------------

def preprocess_image(img_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load and preprocess image for BEVFusion inference.

    Matches V2XDataset.sample_ida_augmentation with bot_pct_lim=(0, 0):
    resize so that max(fH/origH, fW/origW) fills the short side, then crop
    the bottom fH rows and center fW columns.

    Returns:
        img_tensor: np.ndarray [1, 3, FINAL_H, FINAL_W] float32
        ida_mat: np.ndarray [4, 4] float64 - image augmentation matrix
    """
    assert FINAL_H is not None and FINAL_W is not None, \
        "FINAL_H/W must be initialized from the compiled ONNX before calling preprocess_image"

    img = Image.open(img_path)
    orig_w, orig_h = img.size  # PIL: (W, H)

    # Compute resize / crop (same as V2XDataset val augmentation)
    resize = max(FINAL_H / orig_h, FINAL_W / orig_w)
    resize_dims = (int(orig_w * resize), int(orig_h * resize))
    newW, newH = resize_dims
    crop_h = int(newH) - FINAL_H  # bot_pct_lim = (0, 0)
    crop_w = int(max(0, newW - FINAL_W) / 2)
    crop = (crop_w, crop_h, crop_w + FINAL_W, crop_h + FINAL_H)

    img = img.resize(resize_dims)
    img = img.crop(crop)
    # No flip, no rotation for val

    # Build ida_mat
    ida_rot = np.eye(2, dtype=np.float64) * resize
    ida_tran = -np.array([crop[0], crop[1]], dtype=np.float64)
    ida_mat = np.eye(4, dtype=np.float64)
    ida_mat[:2, :2] = ida_rot
    ida_mat[:2, 3] = ida_tran

    # Match mmcv.imnormalize(np.array(PIL_img), mean, std, to_rgb=True):
    # PIL loads as RGB. mmcv's to_rgb=True applies cv2.cvtColor(BGR2RGB) which
    # swaps channels 0 and 2. On a PIL RGB array this produces [B, G, R] order.
    # The model was trained with this channel swap, so we must replicate it.
    img_np = np.array(img, dtype=np.float32)
    img_np = img_np[:, :, ::-1].copy()  # RGB -> BGR (same as cv2.COLOR_BGR2RGB on RGB input)
    img_np = (img_np - IMG_MEAN) / IMG_STD

    # HWC -> CHW
    img_np = img_np.transpose(2, 0, 1).astype(np.float32)

    # Shape: [B=1, C=3, H, W] (NCHW)
    img_tensor = img_np[np.newaxis, ...]
    return img_tensor, ida_mat


# ---------------------------------------------------------------------------
# 3. Voxelization (pure numpy)
# ---------------------------------------------------------------------------

def voxelize_points(points: np.ndarray,
                    voxel_size=None,
                    pc_range=None,
                    max_num_points=None,
                    max_voxels=None) -> Tuple[np.ndarray, np.ndarray]:
    """Hard voxelization in pure numpy.

    Args:
        points: [N, C] float32 point cloud

    Returns:
        voxel_features: [M, C] float32 (averaged per voxel)
        voxel_indices:  [M, 4] int32 (batch_idx, z, y, x)

    Notes:
        The voxel_size / pc_range / max_num_points / max_voxels defaults are
        resolved at CALL TIME from the module globals (which may have been
        updated by init_dataset_geometry_from_onnx). Do NOT write them as
        default parameter values — Python binds those at def-time, which
        produces silent per-dataset voxel miscalibration.
    """
    if voxel_size is None:
        voxel_size = VOXEL_SIZE
    if pc_range is None:
        pc_range = POINT_CLOUD_RANGE
    if max_num_points is None:
        max_num_points = MAX_NUM_POINTS
    if max_voxels is None:
        max_voxels = MAX_VOXELS_TEST
    voxel_size = np.array(voxel_size, dtype=np.float32)
    range_min = np.array(pc_range[:3], dtype=np.float32)
    range_max = np.array(pc_range[3:], dtype=np.float32)
    grid_size = np.round((range_max - range_min) / voxel_size).astype(np.int32)

    # Pre-allocate
    voxels = np.zeros((max_voxels, max_num_points, points.shape[1]), dtype=np.float32)
    coors = np.zeros((max_voxels, 3), dtype=np.int32)  # x, y, z (matching CUDA Voxelization output)
    counts = np.zeros(max_voxels, dtype=np.int32)

    # Hash map: voxel coordinate -> voxel index
    voxel_map = {}
    voxel_num = 0

    for i in range(len(points)):
        pt = points[i]
        # Compute voxel coordinates (x, y, z)
        cx = int(np.floor((pt[0] - range_min[0]) / voxel_size[0]))
        cy = int(np.floor((pt[1] - range_min[1]) / voxel_size[1]))
        cz = int(np.floor((pt[2] - range_min[2]) / voxel_size[2]))

        # Bounds check
        if cx < 0 or cx >= grid_size[0]:
            continue
        if cy < 0 or cy >= grid_size[1]:
            continue
        if cz < 0 or cz >= grid_size[2]:
            continue

        key = (cx, cy, cz)
        if key in voxel_map:
            idx = voxel_map[key]
        else:
            if voxel_num >= max_voxels:
                continue
            idx = voxel_num
            voxel_map[key] = idx
            coors[idx] = [cx, cy, cz]  # (x, y, z) order — matches this codebase's convention
            voxel_num += 1

        n = counts[idx]
        if n < max_num_points:
            voxels[idx, n] = pt
            counts[idx] = n + 1

    voxels = voxels[:voxel_num]
    coors = coors[:voxel_num]
    counts = counts[:voxel_num]

    # Average features per voxel
    features = voxels.sum(axis=1) / np.maximum(counts[:, np.newaxis], 1).astype(np.float32)

    # Add batch index (0) as first column
    batch_idx = np.zeros((voxel_num, 1), dtype=np.int32)
    voxel_indices = np.concatenate([batch_idx, coors], axis=1)  # [M, 4]

    return features.astype(np.float32), voxel_indices.astype(np.int32)


# ---------------------------------------------------------------------------
# 4. BEVPool V2 geometry loading
# ---------------------------------------------------------------------------

def load_geometry(geometry_dir: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load precomputed BEVPool V2 geometry from binary files.

    intervals format: (start, end, bev_rank) — matching SYCL kernel convention.
    """
    # indices
    with open(os.path.join(geometry_dir, "indices.bin"), "rb") as f:
        count = struct.unpack("I", f.read(4))[0]
        indices = np.frombuffer(f.read(count * 4), dtype=np.uint32).astype(np.int32)
    print(f"  Loaded {len(indices)} indices")

    # intervals: (start, end, bev_rank)
    with open(os.path.join(geometry_dir, "intervals.bin"), "rb") as f:
        count = struct.unpack("I", f.read(4))[0]
        intervals = np.frombuffer(f.read(count * 3 * 4), dtype=np.int32).reshape(count, 3).copy()

    n_sentinel = int((intervals[:, 2] < 0).sum())
    print(f"  Loaded {len(intervals)} intervals ({n_sentinel} sentinel with rank=-1)")

    return indices, intervals


# ---------------------------------------------------------------------------
# 5. OpenVINO inference
# ---------------------------------------------------------------------------

def run_inference(compiled_model, img, indices, intervals, voxel_features, voxel_indices):
    """Run unified ONNX model inference.

    Use positional (index-based) input binding because the ONNX merge step
    prefixes some input names (e.g. 'indices' -> 'cam/indices.1').
    """
    input_keys = [inp for inp in compiled_model.inputs]

    # Backward-compatible image rank adaptation:
    # - New unified ONNX expects img as 4-D [B, C, H, W]
    # - Older unified ONNX may expect 5-D [B, N, C, H, W]
    expected_rank = len(input_keys[0].partial_shape)
    if expected_rank == 4 and img.ndim == 5:
        # [B, N, C, H, W] -> [B, C, H, W], assuming single camera N=1
        img = img[:, 0, ...]
    elif expected_rank == 5 and img.ndim == 4:
        # [B, C, H, W] -> [B, N, C, H, W], single camera N=1
        img = img[:, np.newaxis, ...]

    inputs = {
        input_keys[0]: img,
        input_keys[1]: indices,
        input_keys[2]: intervals,
        input_keys[3]: voxel_features,
        input_keys[4]: voxel_indices,
    }
    return compiled_model.infer_new_request(inputs)


def get_output(ov_outputs, name):
    """Get output tensor from OV results by name."""
    for key, val in ov_outputs.items():
        key_name = key.any_name if hasattr(key, "any_name") else str(key)
        if key_name == name:
            return np.array(val)
    raise KeyError(f"Output '{name}' not found. Available: "
                   f"{[k.any_name if hasattr(k, 'any_name') else str(k) for k in ov_outputs]}")


# ---------------------------------------------------------------------------
# 6. CenterHead post-processing (standalone)
# ---------------------------------------------------------------------------

def _topk(heatmap: np.ndarray, K: int = 500):
    """Extract top-K predictions from heatmap.

    Args:
        heatmap: [B, C, H, W] float32 (after sigmoid)
        K: number of top predictions

    Returns:
        scores: [B, K]
        inds: [B, K] - flattened index in C*H*W
        clses: [B, K] - class index
        ys: [B, K] - y coordinate in feature map
        xs: [B, K] - x coordinate in feature map
    """
    B, C, H, W = heatmap.shape
    # Reshape to [B, C*H*W]
    heatmap_flat = heatmap.reshape(B, -1)

    # TopK
    topk_inds = np.argsort(-heatmap_flat, axis=1)[:, :K]
    topk_scores = np.take_along_axis(heatmap_flat, topk_inds, axis=1)

    topk_clses = topk_inds // (H * W)
    topk_inds_in_map = topk_inds % (H * W)
    # Matches CenterPointBBoxCoder: xs = ind // W (row index → x world), ys = ind % W (col index → y world)
    topk_xs = topk_inds_in_map // W
    topk_ys = topk_inds_in_map % W

    return topk_scores, topk_inds, topk_clses, topk_ys.astype(np.float32), topk_xs.astype(np.float32)


def _gather_feat(feat: np.ndarray, inds: np.ndarray) -> np.ndarray:
    """Gather features at specific indices.

    Args:
        feat: [B, C, H, W]
        inds: [B, K] - flattened indices in C*H*W space

    Returns:
        gathered: [B, K, C']
    """
    B, C, H, W = feat.shape
    # feat -> [B, C, H*W] -> transpose -> [B, H*W, C]
    feat_flat = feat.reshape(B, C, H * W).transpose(0, 2, 1)  # [B, H*W, C]

    # inds are in C*H*W space, we need H*W space
    inds_in_map = inds % (H * W)

    # Gather
    gathered = np.zeros((B, inds.shape[1], C), dtype=feat.dtype)
    for b in range(B):
        gathered[b] = feat_flat[b, inds_in_map[b]]
    return gathered


def decode_centerhead(ov_outputs: dict, num_tasks: int = 2) -> List[dict]:
    """Decode CenterHead predictions from ONNX output tensors.

    Returns list of dicts per task: {bboxes, scores, labels}
    """
    pc_range = np.array(POINT_CLOUD_RANGE)
    voxel_size = np.array(VOXEL_SIZE[:2])

    results_per_task = []
    class_offset = 0

    for t in range(num_tasks):
        heatmap = get_output(ov_outputs, f"task{t}_heatmap")  # [B, C, H, W]
        reg = get_output(ov_outputs, f"task{t}_reg")          # [B, 2, H, W]
        height = get_output(ov_outputs, f"task{t}_height")    # [B, 1, H, W]
        dim = get_output(ov_outputs, f"task{t}_dim")          # [B, 3, H, W]
        rot = get_output(ov_outputs, f"task{t}_rot")          # [B, 2, H, W]
        vel = get_output(ov_outputs, f"task{t}_vel")          # [B, 2, H, W]

        B, num_cls, H, W = heatmap.shape

        # Sigmoid
        heatmap = 1.0 / (1.0 + np.exp(-heatmap.clip(-10, 10)))

        # TopK
        scores, inds, clses, ys, xs = _topk(heatmap, K=MAX_NUM_DETECTIONS)

        # Refine with regression offsets
        reg_gathered = _gather_feat(reg, inds)     # [B, K, 2]
        xs = xs[:, :, np.newaxis] + reg_gathered[:, :, 0:1]
        ys = ys[:, :, np.newaxis] + reg_gathered[:, :, 1:2]

        # Height
        hei = _gather_feat(height, inds)           # [B, K, 1]

        # Dimensions (log-encoded if norm_bbox=True)
        dim_pred = _gather_feat(dim, inds)         # [B, K, 3]
        dim_pred = np.exp(dim_pred)  # norm_bbox=True

        # Rotation
        rot_pred = _gather_feat(rot, inds)         # [B, K, 2]
        rot_angle = np.arctan2(rot_pred[:, :, 0:1], rot_pred[:, :, 1:2])

        # Velocity
        vel_pred = _gather_feat(vel, inds)         # [B, K, 2]

        # Convert feature map coordinates to world coordinates
        xs = xs * OUT_SIZE_FACTOR * voxel_size[0] + pc_range[0]
        ys = ys * OUT_SIZE_FACTOR * voxel_size[1] + pc_range[1]

        # Assemble boxes: [x, y, z, w, h, l, yaw, vx, vy]
        boxes = np.concatenate([xs, ys, hei, dim_pred, rot_angle, vel_pred], axis=2)

        # Process batch (B=1)
        for b in range(B):
            box_b = boxes[b]        # [K, 9]
            score_b = scores[b]     # [K]
            cls_b = clses[b]        # [K]

            # Score threshold
            mask = score_b > SCORE_THRESHOLD
            # Post center range
            center_mask = (
                (box_b[:, 0] >= POST_CENTER_RANGE[0]) &
                (box_b[:, 0] <= POST_CENTER_RANGE[3]) &
                (box_b[:, 1] >= POST_CENTER_RANGE[1]) &
                (box_b[:, 1] <= POST_CENTER_RANGE[4]) &
                (box_b[:, 2] >= POST_CENTER_RANGE[2]) &
                (box_b[:, 2] <= POST_CENTER_RANGE[5])
            )
            mask = mask & center_mask

            box_b = box_b[mask]
            score_b = score_b[mask]
            cls_b = cls_b[mask]

            results_per_task.append({
                "bboxes": box_b,
                "scores": score_b,
                "labels": cls_b + class_offset,
            })

        class_offset += len(TASKS[t])

    return results_per_task


def circle_nms(dets: np.ndarray, thresh: float, post_max_size: int = 83) -> np.ndarray:
    """Circle NMS: suppress based on center distance.

    Args:
        dets: [N, 3] with (x, y, score)
        thresh: squared distance threshold
        post_max_size: max detections to keep
    """
    if len(dets) == 0:
        return np.array([], dtype=np.int64)

    x1 = dets[:, 0]
    y1 = dets[:, 1]
    sc = dets[:, 2]
    order = sc.argsort()[::-1]

    suppressed = np.zeros(len(dets), dtype=np.int32)
    keep = []

    for ii in range(len(order)):
        i = order[ii]
        if suppressed[i]:
            continue
        keep.append(i)
        for jj in range(ii + 1, len(order)):
            j = order[jj]
            if suppressed[j]:
                continue
            dist = (x1[i] - x1[j]) ** 2 + (y1[i] - y1[j]) ** 2
            if dist <= thresh:
                suppressed[j] = 1

    return np.array(keep[:post_max_size], dtype=np.int64)


def rotate_nms_numpy(boxes_xyxyr: np.ndarray, scores: np.ndarray,
                     thresh: float, pre_max_size: int = 1000,
                     post_max_size: int = 83) -> np.ndarray:
    """Rotate NMS approximation using axis-aligned IoU.

    For a fully correct implementation, use GPU rotate IoU NMS.
    This is a reasonable CPU approximation that works for most cases.

    Args:
        boxes_xyxyr: [N, 5] (x1, y1, x2, y2, rotation)
        scores: [N]
        thresh: IoU threshold
    """
    if len(boxes_xyxyr) == 0:
        return np.array([], dtype=np.int64)

    # Sort by score descending
    order = scores.argsort()[::-1]
    if pre_max_size is not None:
        order = order[:pre_max_size]

    x1 = boxes_xyxyr[order, 0]
    y1 = boxes_xyxyr[order, 1]
    x2 = boxes_xyxyr[order, 2]
    y2 = boxes_xyxyr[order, 3]
    areas = (x2 - x1) * (y2 - y1)

    suppressed = np.zeros(len(order), dtype=np.int32)
    keep = []

    for ii in range(len(order)):
        if suppressed[ii]:
            continue
        keep.append(order[ii])
        for jj in range(ii + 1, len(order)):
            if suppressed[jj]:
                continue
            xx1 = max(x1[ii], x1[jj])
            yy1 = max(y1[ii], y1[jj])
            xx2 = min(x2[ii], x2[jj])
            yy2 = min(y2[ii], y2[jj])
            w = max(0, xx2 - xx1)
            h = max(0, yy2 - yy1)
            inter = w * h
            union = areas[ii] + areas[jj] - inter
            if union > 0 and inter / union > thresh:
                suppressed[jj] = 1

    keep = np.array(keep[:post_max_size], dtype=np.int64)
    return keep


def xywhr2xyxyr(boxes_xywhr: np.ndarray) -> np.ndarray:
    """Convert (x, y, w, h, rotation) to (x1, y1, x2, y2, rotation)."""
    out = np.zeros_like(boxes_xywhr)
    half_w = boxes_xywhr[:, 2] / 2
    half_h = boxes_xywhr[:, 3] / 2
    out[:, 0] = boxes_xywhr[:, 0] - half_w
    out[:, 1] = boxes_xywhr[:, 1] - half_h
    out[:, 2] = boxes_xywhr[:, 0] + half_w
    out[:, 3] = boxes_xywhr[:, 1] + half_h
    out[:, 4] = boxes_xywhr[:, 4]
    return out


def apply_nms(results_per_task: List[dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply per-task NMS and merge results.

    Returns:
        bboxes: [N, 9]
        scores: [N]
        labels: [N]
    """
    all_bboxes = []
    all_scores = []
    all_labels = []

    for t, result in enumerate(results_per_task):
        bboxes = result["bboxes"]
        scores = result["scores"]
        labels = result["labels"]

        if len(scores) == 0:
            continue

        nms_type = NMS_TYPE[t] if t < len(NMS_TYPE) else "rotate"

        if nms_type == "circle":
            # PyTorch uses min_radius[task_id] for the whole task, not per-class
            radius = MIN_RADIUS[t] if t < len(MIN_RADIUS) else MIN_RADIUS[-1]
            dets = np.column_stack([bboxes[:, 0], bboxes[:, 1], scores])
            keep = circle_nms(dets, thresh=radius, post_max_size=POST_MAX_SIZE)
            if len(keep) == 0:
                continue
            bboxes, scores, labels = bboxes[keep], scores[keep], labels[keep]

        else:
            # Rotate NMS
            # BEV format: [x, y, w, h, yaw]
            bev = bboxes[:, [0, 1, 3, 4, 6]]
            boxes_for_nms = xywhr2xyxyr(bev)
            keep = rotate_nms_numpy(boxes_for_nms, scores,
                                    thresh=NMS_THR,
                                    pre_max_size=PRE_MAX_SIZE,
                                    post_max_size=POST_MAX_SIZE)
            if len(keep) == 0:
                continue
            bboxes = bboxes[keep]
            scores = scores[keep]
            labels = labels[keep]

        all_bboxes.append(bboxes)
        all_scores.append(scores)
        all_labels.append(labels)

    if len(all_bboxes) == 0:
        return np.zeros((0, 9), dtype=np.float32), np.array([]), np.array([], dtype=np.int64)

    bboxes = np.concatenate(all_bboxes, axis=0)
    scores = np.concatenate(all_scores, axis=0)
    labels = np.concatenate(all_labels, axis=0)

    # Adjust Z: from bottom to gravity center
    bboxes[:, 2] = bboxes[:, 2] - bboxes[:, 5] * 0.5

    return bboxes, scores, labels


# ---------------------------------------------------------------------------
# 7. 3D box corners computation (standalone)
# ---------------------------------------------------------------------------

def rotation_3d_z(angles: np.ndarray) -> np.ndarray:
    """Build rotation matrices around Z axis.

    Args:
        angles: [N] rotation angles

    Returns:
        [N, 3, 3] rotation matrices
    """
    s = np.sin(angles)
    c = np.cos(angles)
    z = np.zeros_like(angles)
    o = np.ones_like(angles)
    # [[cos, -sin, 0], [sin, cos, 0], [0, 0, 1]]
    R = np.stack([
        np.stack([c, -s, z], axis=-1),
        np.stack([s, c, z], axis=-1),
        np.stack([z, z, o], axis=-1),
    ], axis=-2)
    return R


def box3d_corners(bboxes: np.ndarray) -> np.ndarray:
    """Compute 8 corners for each 3D box.

    Args:
        bboxes: [N, 9] (x, y, z, w, h, l, yaw, vx, vy)
            z is gravity center, w=x_size, h=y_size, l=z_size

    Returns:
        corners: [N, 8, 3]
    """
    if len(bboxes) == 0:
        return np.zeros((0, 8, 3), dtype=np.float32)

    centers = bboxes[:, :3]
    dims = bboxes[:, 3:6]  # w, h, l (x_size, y_size, z_size)
    yaws = bboxes[:, 6]

    # 8 corner offsets (same order as LiDARInstance3DBoxes)
    # indices: 0,1,3,2,4,5,7,6 from unravel_index of [2,2,2]
    idx = np.array([[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0],
                    [1, 0, 0], [1, 0, 1], [1, 1, 1], [1, 1, 0]], dtype=np.float32)
    # origin at (0.5, 0.5, 0)
    idx = idx - np.array([0.5, 0.5, 0.0])

    # corners = dims * offsets
    corners = dims[:, np.newaxis, :] * idx[np.newaxis, :, :]  # [N, 8, 3]

    # Rotate around z axis to match LiDARInstance3DBoxes.corners convention.
    # mmdet3d uses R_matT = standard(angle=-yaw-pi/2) with einsum("aij,jka->aik"),
    # which is equivalent to applying standard R(+yaw+pi/2) on the left.
    rot_angles = yaws + np.pi / 2
    R = rotation_3d_z(rot_angles)  # [N, 3, 3]
    corners = np.einsum("nij,nmj->nmi", R, corners)

    # Translate
    corners = corners + centers[:, np.newaxis, :]

    return corners


# ---------------------------------------------------------------------------
# 8. Visualization (standalone, no mmdet3d)
# ---------------------------------------------------------------------------

def visualize_camera(fpath: str, image: np.ndarray, bboxes: np.ndarray,
                     labels: np.ndarray, lidar2cam: np.ndarray,
                     cam_intrinsic: np.ndarray, classes: List[str],
                     thickness: int = 4):
    """Draw 3D bounding boxes on camera image.

    Args:
        image: [H, W, 3] RGB uint8
        bboxes: [N, 9]
        labels: [N] int
        lidar2cam: [4, 4]
        cam_intrinsic: [4, 4] (padded intrinsic)
    """
    canvas = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    if len(bboxes) > 0:
        corners = box3d_corners(bboxes)  # [N, 8, 3]
        N = corners.shape[0]

        # Homogeneous coordinates
        coords = np.concatenate([
            corners.reshape(-1, 3),
            np.ones((N * 8, 1), dtype=np.float32)
        ], axis=-1)  # [N*8, 4]

        # Transform: lidar -> camera
        coords = coords @ lidar2cam.T  # [N*8, 4]

        # Project: camera -> image
        coords = coords @ cam_intrinsic.T  # [N*8, 4]

        coords = coords.reshape(N, 8, 4)

        # Filter: all corners must be in front of camera
        in_front = np.all(coords[:, :, 2] > 0, axis=1)
        coords = coords[in_front]
        valid_labels = labels[in_front]

        # Sort by depth (far to near for correct drawing order)
        sort_idx = np.argsort(-np.min(coords[:, :, 2], axis=1))
        coords = coords[sort_idx]
        valid_labels = valid_labels[sort_idx]

        # Perspective divide
        coords_flat = coords.reshape(-1, 4)
        coords_flat[:, 2] = np.clip(coords_flat[:, 2], 1e-5, 1e5)
        coords_flat[:, 0] /= coords_flat[:, 2]
        coords_flat[:, 1] /= coords_flat[:, 2]
        coords_2d = coords_flat[:, :2].reshape(-1, 8, 2)

        edges = [(0, 1), (0, 3), (0, 4), (1, 2), (1, 5), (3, 2), (3, 7),
                 (4, 5), (4, 7), (2, 6), (5, 6), (6, 7)]

        for i in range(coords_2d.shape[0]):
            lbl = int(valid_labels[i])
            name = classes[lbl] if lbl < len(classes) else "unknown"
            color = OBJECT_PALETTE.get(name, (255, 255, 255))
            # BGR for cv2
            color_bgr = (color[2], color[1], color[0])

            for s, e in edges:
                pt1 = tuple(coords_2d[i, s].astype(np.int32))
                pt2 = tuple(coords_2d[i, e].astype(np.int32))
                cv2.line(canvas, pt1, pt2, color_bgr, thickness, cv2.LINE_AA)

    canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    cv2.imwrite(fpath, cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))


def visualize_lidar(fpath: str, lidar: np.ndarray, bboxes: np.ndarray,
                    labels: np.ndarray, classes: List[str],
                    xlim=(0, 102.4), ylim=(-51.2, 51.2),
                    radius=15, thickness=25):
    """Draw lidar BEV with 3D box outlines."""
    fig = plt.figure(figsize=(xlim[1] - xlim[0], ylim[1] - ylim[0]))
    ax = plt.gca()
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect(1)
    ax.set_axis_off()

    if lidar is not None and len(lidar) > 0:
        plt.scatter(lidar[:, 0], lidar[:, 1], s=radius, c="white")

    if len(bboxes) > 0:
        corners = box3d_corners(bboxes)  # [N, 8, 3]
        # BEV outline: corners 0,3,7,4,0 (bottom face)
        outline = corners[:, [0, 3, 7, 4, 0], :2]
        for i in range(outline.shape[0]):
            lbl = int(labels[i])
            name = classes[lbl] if lbl < len(classes) else "unknown"
            color = OBJECT_PALETTE.get(name, (255, 255, 255))
            plt.plot(outline[i, :, 0], outline[i, :, 1],
                     linewidth=thickness,
                     color=np.array(color) / 255.0)

    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    fig.savefig(fpath, dpi=10, facecolor="black", format="png",
                bbox_inches="tight", pad_inches=0)
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    if args.ann_file is None:
        args.ann_file = os.path.join(args.data_root, "dair_12hz_infos_val.pkl")

    print("=" * 60)
    print("  BEVFusion Standalone Inference (OpenVINO)")
    print("=" * 60)
    print(f"  data_root    : {args.data_root}")
    print(f"  ann_file     : {args.ann_file}")
    print(f"  onnx_path    : {args.onnx_path}")
    print(f"  geometry_dir : {args.geometry_dir}")
    print(f"  device       : {args.device}")
    print(f"  out_dir      : {args.out_dir}")
    print()

    # ---- Load annotations ----
    print("[1/4] Loading annotations ...")
    infos = load_annotations(args.ann_file)
    print(f"  {len(infos)} samples loaded")

    # ---- Load geometry ----
    print("[2/4] Loading BEVPool V2 geometry ...")
    geom_indices, geom_intervals = load_geometry(args.geometry_dir)

    # ---- Load OpenVINO model ----
    print("[3/4] Loading ONNX model via OpenVINO ...")
    core = ov.Core()
    # NOTE: Do NOT set INFERENCE_PRECISION_HINT=FP32 — it triggers a bug in the
    # SYCL SparseConvolution kernel's FP32 path (cosine drops to ~0.34).
    core.set_property({"PERFORMANCE_HINT": "LATENCY"})

    try:
        compiled_model = core.compile_model(args.onnx_path, device_name=args.device)
    except RuntimeError as e:
        print(f"\n  ERROR: Failed to compile model on {args.device}")
        print(f"  {e}")
        if "SparseConvolution" in str(e):
            print("\n  Note: SparseConvolution/SparseToDense require Intel GPU (SYCL).")
            print("  Make sure you are running on a machine with Intel Arc GPU")
            print("  and the custom OpenVINO build.")
        sys.exit(1)

    print("  Model inputs:")
    for i, inp in enumerate(compiled_model.inputs):
        print(f"    [{i}] {inp.any_name:30s}  {inp.partial_shape}  {inp.element_type}")
    print("  Model outputs:")
    for i, out in enumerate(compiled_model.outputs):
        print(f"    [{i}] {out.any_name:30s}  {out.partial_shape}  {out.element_type}")

    # Read FINAL_H/W from the compiled img input so this script works for any
    # dataset (V2X-I 864x1536, KITTI 384x1280, etc.) without edits.
    global FINAL_H, FINAL_W
    img_shape = compiled_model.inputs[0].partial_shape
    img_rank = len(img_shape)
    FINAL_H = int(img_shape[img_rank - 2].get_length())
    FINAL_W = int(img_shape[img_rank - 1].get_length())
    print(f"  Using FINAL_H={FINAL_H}, FINAL_W={FINAL_W} (from ONNX img input)")

    # Auto-detect pc_range / voxel_size / sparse_shape from ONNX attrs so the
    # same script works on KITTI / V2X-I / nuScenes without manual edits.
    # (This prevents the ghost-detection bug caused by mixing V2X range with
    #  a KITTI-exported ONNX.)
    init_dataset_geometry_from_onnx(args.onnx_path)
    # print()

    # ---- Inference loop ----
    print("[4/4] Running inference ...")
    os.makedirs(os.path.join(args.out_dir, "camera"), exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, "lidar"), exist_ok=True)

    num_tasks = len(TASKS)
    total = min(len(infos), args.max_samples) if args.max_samples else len(infos)

    for idx in range(total):
        info = infos[idx]
        token = info.get("sample_token", f"sample_{idx:05d}")
        name = token.split("/")[-1].split(".")[0] if "/" in token else token

        # ---- Load image ----
        cam_info = info["cam_infos"]
        cam_key = list(cam_info.keys())[0]  # "CAM_FRONT"
        img_file = cam_info[cam_key]["filename"]
        img_path = os.path.join(args.data_root, img_file)

        img_tensor, ida_mat = preprocess_image(img_path)

        # ---- Load point cloud ----
        lidar_info = info["lidar_infos"]
        lidar_key = list(lidar_info.keys())[0]  # "LIDAR_TOP"
        pcd_file = lidar_info[lidar_key]["filename"]
        pcd_path = os.path.join(args.data_root, pcd_file)
        points = load_pointcloud(pcd_path)

        # Use only first 4 channels (x, y, z, intensity)
        if points.shape[1] > 4:
            points = points[:, :4]

        # ---- Voxelize ----
        voxel_features, voxel_indices = voxelize_points(points)
        print(f"  [{name}] points: {points.shape[0]}, "
              f"voxels: {voxel_features.shape[0]}")

        # ---- Diagnostics before inference ----
        if idx == 0:
            print(f"  [diag] img_tensor: shape={img_tensor.shape}, dtype={img_tensor.dtype}, "
                  f"min={img_tensor.min():.2f}, max={img_tensor.max():.2f}")
            print(f"  [diag] geom_indices: shape={geom_indices.shape}, dtype={geom_indices.dtype}, "
                  f"min={geom_indices.min()}, max={geom_indices.max()}")
            print(f"  [diag] geom_intervals: shape={geom_intervals.shape}, dtype={geom_intervals.dtype}")
            print(f"         col0(start): min={geom_intervals[:,0].min()}, max={geom_intervals[:,0].max()}")
            print(f"         col1(end):   min={geom_intervals[:,1].min()}, max={geom_intervals[:,1].max()}")
            print(f"         col2(bev):   min={geom_intervals[:,2].min()}, max={geom_intervals[:,2].max()}")
            print(f"  [diag] voxel_features: shape={voxel_features.shape}, dtype={voxel_features.dtype}, "
                  f"min={voxel_features.min():.2f}, max={voxel_features.max():.2f}")
            print(f"  [diag] voxel_indices: shape={voxel_indices.shape}, dtype={voxel_indices.dtype}")
            print(f"         col0(batch): min={voxel_indices[:,0].min()}, max={voxel_indices[:,0].max()}")
            print(f"         col1: min={voxel_indices[:,1].min()}, max={voxel_indices[:,1].max()}")
            print(f"         col2: min={voxel_indices[:,2].min()}, max={voxel_indices[:,2].max()}")
            print(f"         col3: min={voxel_indices[:,3].min()}, max={voxel_indices[:,3].max()}")
            sys.stdout.flush()

        # ---- Run OpenVINO ----
        ov_outputs = run_inference(
            compiled_model, img_tensor, geom_indices, geom_intervals,
            voxel_features, voxel_indices,
        )

        if idx == 0:
            print("  Output keys:")
            for key in ov_outputs:
                kn = key.any_name if hasattr(key, "any_name") else str(key)
                print(f"    {kn:40s}  shape={ov_outputs[key].shape}")

        # ---- Decode & NMS ----
        results_per_task = decode_centerhead(ov_outputs, num_tasks)
        bboxes, scores, labels = apply_nms(results_per_task)
        num_after_nms = len(scores)

        # ---- Score filter ----
        if args.bbox_score is not None and len(scores) > 0:
            mask = scores >= args.bbox_score
            bboxes = bboxes[mask]
            scores = scores[mask]
            labels = labels[mask]

        # Print AFTER score filter so terminal matches visualization.
        # Include pre-filter count for debugging when --bbox-score is set.
        if args.bbox_score is not None:
            print(f"  [{name}] Detections: {len(scores)} boxes "
                  f"(score >= {args.bbox_score}, {num_after_nms} before filter)")
        else:
            print(f"  [{name}] Detections: {len(scores)} boxes")

        # ---- Visualize camera ----
        raw_img = np.array(Image.open(img_path))

        # Build lidar2camera and camera intrinsic matrices
        lidar2cam = load_lidar2camera(args.data_root, pcd_file)

        # Camera intrinsic (padded to 4x4)
        cam_intrinsic_3x3 = np.array(
            cam_info[cam_key]["calibrated_sensor"]["camera_intrinsic"],
            dtype=np.float64,
        )
        cam_intrinsic = np.eye(4, dtype=np.float64)
        cam_intrinsic[:3, :3] = cam_intrinsic_3x3

        visualize_camera(
            os.path.join(args.out_dir, "camera", f"{name}.png"),
            raw_img, bboxes, labels,
            lidar2cam, cam_intrinsic,
            OBJECT_CLASSES,
        )

        # ---- Visualize lidar BEV ----
        visualize_lidar(
            os.path.join(args.out_dir, "lidar", f"{name}.png"),
            points, bboxes, labels,
            OBJECT_CLASSES,
            xlim=[POINT_CLOUD_RANGE[0], POINT_CLOUD_RANGE[3]],
            ylim=[POINT_CLOUD_RANGE[1], POINT_CLOUD_RANGE[4]],
        )

    print(f"\nDone! Results saved to: {args.out_dir}")


if __name__ == "__main__":
    main()
