#!/usr/bin/env python3
"""Accuracy-controlled INT8 quantization of bevfusion_unified.onnx with NNCF.

Runs in /home/jie/env/spconvEnv/bin/python (py3.12 + torch 2.11 + openvino 2026.1
+ nncf 2.13). Loads the custom OpenVINO build from /home/jie/workspace/openvino
on sys.path so the graph's three custom ops (BevPoolV2, SparseConvolution,
SparseToDense) resolve.

Calibration prerequisites (run once with bevEnv first):
  # indices.bin / intervals.bin
  python export/precompute_geometry.py <config> <ckpt> -o export/geometry
  # voxel_features/voxel_indices/img per frame
  python export/dump_voxels.py <config> <ckpt> -o export/calib_voxels --num-frames 400

The unified ONNX has 5 inputs; three of them are int32 index streams that must
NOT be quantized, and 23 nodes are custom ops that OpenVINO keeps FP-only:
  - cam/BevPoolV2_125
  - lidar/conv0 ... lidar/conv20        (21 x SparseConvolution)
  - lidar/sparse_to_dense               (SparseToDense)

Usage:
  # V2X-I (legacy default — hard-coded coder constants):
  /home/jie/env/spconvEnv/bin/python export/quantize_unified.py [--smoke]

  # KITTI — must pass --config so coder constants come from the cfg:
  /home/jie/env/spconvEnv/bin/python export/quantize_unified.py \
      --config configs/Kitti/det/centerhead/secfpn/camera+lidar/default.yaml [--smoke]
"""

# ---------------------------------------------------------------------------
# 1. Bootstrap the custom OpenVINO build BEFORE importing openvino
# ---------------------------------------------------------------------------
import os
import sys

OV_ROOT = os.environ.get(
    "OPENVINO_CUSTOM_ROOT", "/home/jie/workspace/openvino/bin/intel64/Release"
)
if os.path.isdir(os.path.join(OV_ROOT, "python")):
    sys.path.insert(0, os.path.join(OV_ROOT, "python"))
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    if OV_ROOT not in ld.split(":"):
        os.environ["LD_LIBRARY_PATH"] = OV_ROOT + (":" + ld if ld else "")

import argparse
import glob
import struct
import time
import types
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, List, Tuple

import numpy as np
import openvino as ov

# --- Compatibility shim: NNCF 2.13 still imports `openvino.runtime`, but the
# custom 2026.1 build dropped that submodule. Stitch it back together from the
# top-level `openvino` namespace so nncf's backend detector finds the package.
if "openvino.runtime" not in sys.modules:
    _rt = types.ModuleType("openvino.runtime")
    # Mirror every public attribute from the top-level openvino module onto
    # openvino.runtime so any `from openvino.runtime import Foo` works.
    for _name in dir(ov):
        if not _name.startswith("_"):
            setattr(_rt, _name, getattr(ov, _name))
    sys.modules["openvino.runtime"] = _rt
    for _n in range(1, 17):
        try:
            _op = __import__(f"openvino.opset{_n}", fromlist=[""])
            sys.modules[f"openvino.runtime.opset{_n}"] = _op
            setattr(_rt, f"opset{_n}", _op)
        except ModuleNotFoundError:
            pass
    # Some NNCF paths reach in for _pyopenvino or ops submodule — expose them.
    import openvino._pyopenvino as _pyov  # noqa: F401
    if hasattr(ov, "op"):
        sys.modules["openvino.runtime.op"] = ov.op
        _rt.op = ov.op
    if hasattr(ov, "passes"):
        sys.modules["openvino.runtime.passes"] = ov.passes
        _rt.passes = ov.passes

import nncf

# Register the SparseConvolution op so NNCF PTQ can insert FakeQuantize around
# it instead of silently skipping it. Import ordering matters: NNCF's metatype
# registry must be mutated BEFORE any `nncf.quantize(...)` call. See
# bevfusion/export/_nncf_register_sparseconv.py for the rationale.
#
# `export/` is not a package (no __init__.py) and the script is invoked as
# `python -u export/quantize_unified.py`, so we import the sibling module by
# adding its directory to sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _nncf_register_sparseconv  # noqa: F401,E402

# --- NNCF hardcodes device_name="CPU" for its statistics-collection engine at
# nncf/openvino/engine.py:68. The unified graph contains SparseConvolution
# which has no CPU implementation, so we monkey-patch the engine to use the
# same GPU device we run validation on.
_NNCF_DEVICE = os.environ.get("NNCF_OV_DEVICE", "GPU.1")


def _patch_nncf_engine_device(device: str) -> None:
    """Redirect NNCF's hardcoded CPU compile_model to our GPU, and swap the
    shared-infer-request pattern for `infer_new_request`.

    Two B580 driver workarounds bundled here:
      (a) NNCF pins `device_name="CPU"` in its statistics + accuracy-control
          engines. The unified graph contains SparseConvolution which has no
          CPU implementation, so both compiles must go to the GPU.
      (b) The B580 OpenCL runtime leaks resources when a single infer_request
          is reused across many calls on a graph containing SparseConvolution
          (CL_OUT_OF_RESOURCES around ~20 calls). `infer_new_request` allocates
          a fresh request each call — this is the pattern
          bevfusion_standalone_ov_inference_dump.py already uses at line 260.

    Works for both NNCF 2.13 and 3.1.
    """
    from nncf.openvino import engine as _eng
    from nncf.openvino.graph.model_utils import model_has_state

    # --- (a) redirect CPU compiles to the GPU ------------------------------
    def _native_init(self, model, use_fp32_precision: bool = True):
        import openvino.runtime as _ov
        config = {}
        if use_fp32_precision and hasattr(_ov, "properties"):
            try:
                config = {_ov.properties.hint.inference_precision(): _ov.Type.f32}
            except Exception:
                config = {}
        compiled = _ov.Core().compile_model(model, device_name=device, config=config)
        self.engine = _eng.OVCompiledModelEngine(compiled, model_has_state(model))

    _eng.OVNativeEngine.__init__ = _native_init

    from nncf.quantization.algorithms.accuracy_control import openvino_backend as _acc

    def _prepared_init(self, model, use_fp32_precision: bool = True):
        import openvino.runtime as _ov
        self._stateful = model_has_state(model)
        config = {}
        if use_fp32_precision and hasattr(_ov, "properties"):
            try:
                config = {_ov.properties.hint.inference_precision(): _ov.Type.f32}
            except Exception:
                config = {}
        self._compiled_model = _ov.Core().compile_model(
            model, device_name=device, config=config
        )
        self._engine = None

    _acc.OVPreparedModel.__init__ = _prepared_init

    # --- (b) swap shared infer_request for infer_new_request ---------------
    # Deliberately DO NOT chain the original __init__: it creates a shared
    # infer_request that we never use. Keeping that request alive while we
    # also allocate fresh ones each call leads to `free(): invalid pointer`
    # during NNCF's ranking phase on the B580 driver.
    _reset_key = getattr(_eng, "NNCF_DATASET_RESET_STATE_KEY", None)

    def _cme_init(self, compiled_model, stateful):
        self._compiled_model = compiled_model
        self.reset_state = False  # state reset handled inside infer_new_request
        self._stateful = stateful

    def _cme_infer(self, input_data):
        # Strip NNCF's reset-state sentinel if present — infer_new_request
        # always gives us a fresh state-free request anyway.
        if (
            _reset_key is not None
            and isinstance(input_data, dict)
            and _reset_key in input_data
        ):
            input_data = dict(input_data)
            input_data.pop(_reset_key)
        model_outputs = self._compiled_model.infer_new_request(input_data)
        output_data = {}
        for tensor, value in model_outputs.items():
            for tensor_name in tensor.get_names():
                output_data[tensor_name] = value
        return output_data

    _eng.OVCompiledModelEngine.__init__ = _cme_init
    _eng.OVCompiledModelEngine.infer = _cme_infer


_patch_nncf_engine_device(_NNCF_DEVICE)

# ---------------------------------------------------------------------------
# 2. Paths / constants
# ---------------------------------------------------------------------------
DEFAULT_MODEL_FP32 = "/home/jie/workspace/bev_latest/deploy/data/v2xfusion/onnx/bevfusion_unified.onnx"
DEFAULT_MODEL_INT8 = "/home/jie/workspace/bev_latest/deploy/data/v2xfusion/onnx/bevfusion_unified_int8.xml"

DEFAULT_GEO_DIR = "/home/jie/workspace/bevfusion/export/geometry"
DEFAULT_CALIB_DIR = "/home/jie/workspace/bevfusion/export/calib_voxels"

# CenterHead decode parameters. Either derived from the dataset config
# (when --config is given) or fall back to the legacy V2X-I values for
# backwards compatibility. See decode_params_from_cfg / _v2xi_default below.


@dataclass(frozen=True)
class DecodeParams:
    pc_range: np.ndarray            # shape (6,), float32
    post_center_range: np.ndarray   # shape (6,), float32
    voxel_size: np.ndarray          # shape (2,), float32 — BEV xy only
    out_size_factor: int
    score_threshold: float
    max_num: int
    task_class_offsets: Tuple[int, ...]


def decode_params_from_cfg(cfg) -> "DecodeParams":
    """Read CenterHead decode constants from a loaded mmcv Config."""
    obj = cfg.model.heads.object
    coder = obj.bbox_coder
    offsets: List[int] = []
    cum = 0
    for t in obj.tasks:
        offsets.append(cum)
        cum += len(t)
    return DecodeParams(
        pc_range=np.asarray(coder.pc_range, dtype=np.float32),
        post_center_range=np.asarray(coder.post_center_range, dtype=np.float32),
        voxel_size=np.asarray(list(coder.voxel_size)[:2], dtype=np.float32),
        out_size_factor=int(coder.out_size_factor),
        score_threshold=float(coder.score_threshold),
        max_num=int(coder.max_num),
        task_class_offsets=tuple(offsets),
    )


def decode_params_v2xi_default() -> "DecodeParams":
    """Legacy V2X-I constants used when --config is not provided.

    Lifted from configs/V2X-I/det/centerhead/secfpn/camera+lidar/default.yaml.
    Note: voxel_size=[0.1,0.1] * out_size_factor=8 = 0.8 m/cell here matches
    bbox_coder voxel_size=[0.2,0.2] * out_size_factor=4 in the cfg, so the
    feature-grid spacing is identical; switching to cfg-driven for V2X-I is
    a no-op numerically.
    """
    return DecodeParams(
        pc_range=np.array([0, -51.2, -5, 102.4, 51.2, 3], dtype=np.float32),
        post_center_range=np.array(
            [0.0, -61.2, -10.0, 122.4, 61.2, 10.0], dtype=np.float32),
        voxel_size=np.array([0.1, 0.1], dtype=np.float32),
        out_size_factor=8,
        score_threshold=0.1,
        max_num=500,
        task_class_offsets=(0, 5),
    )


def _build_decode_params(args) -> "DecodeParams":
    if args.config:
        from torchpack.utils.config import configs
        from mmcv import Config
        from mmdet3d.utils import recursive_eval

        configs.load(args.config, recursive=True)
        cfg = Config(recursive_eval(configs), filename=args.config)
        return decode_params_from_cfg(cfg)
    return decode_params_v2xi_default()

DEVICE = "GPU.1"  # Arc B580 — SparseConvolution needs a GPU backend

# Custom ops that must stay FP16/FP32 because the OV GPU plugin has no INT8
# kernel for them and no plan to add one (contribute <2 ms total).
# SparseConvolution used to be in this list, but as of §4 (2026-04-24) we let
# NNCF quantize it — see _nncf_register_sparseconv.py and
# ov_sparse_convolution_int8_optimization.md §4.
IGNORED_SCOPE = nncf.IgnoredScope(
    names=[
        "cam/BevPoolV2_125",
        "lidar/sparse_to_dense",
    ],
    types=["BevPoolV2", "SparseToDense"],
)


# ---------------------------------------------------------------------------
# 3. Geometry + data loaders
# ---------------------------------------------------------------------------
def load_indices(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        n = struct.unpack("I", f.read(4))[0]
        return np.frombuffer(f.read(n * 4), dtype=np.uint32).astype(np.int32)


def load_intervals(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        n = struct.unpack("I", f.read(4))[0]
        return np.frombuffer(f.read(n * 12), dtype=np.int32).reshape(n, 3)


def discover_frames(root: str) -> List[str]:
    manifest = os.path.join(root, "manifest.txt")
    if os.path.exists(manifest):
        with open(manifest) as f:
            return [l.strip() for l in f if l.strip()]
    return sorted(
        os.path.basename(p).replace("_img.npy", "")
        for p in glob.glob(os.path.join(root, "*_img.npy"))
    )


class UnifiedDataset:
    """Yields dicts with all 5 ONNX inputs ready for the OV compiled_model."""

    def __init__(self, frame_ids: List[str], calib_dir: str, geo_dir: str):
        self.frame_ids = frame_ids
        self.calib_dir = calib_dir
        self.indices = load_indices(os.path.join(geo_dir, "indices.bin"))
        self.intervals = load_intervals(os.path.join(geo_dir, "intervals.bin"))

    def __len__(self) -> int:
        return len(self.frame_ids)

    def __iter__(self):
        for fid in self.frame_ids:
            yield self[fid]

    def __getitem__(self, fid):
        if isinstance(fid, int):
            fid = self.frame_ids[fid]
        return dict(
            img=np.load(os.path.join(self.calib_dir, f"{fid}_img.npy")),
            indices=self.indices,
            intervals=self.intervals,
            voxel_features=np.load(os.path.join(self.calib_dir, f"{fid}_voxel_features.npy")),
            voxel_indices=np.load(os.path.join(self.calib_dir, f"{fid}_voxel_indices.npy")),
        )


def transform_fn(sample: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """NNCF feeds each item through this; we already store contiguous arrays."""
    return {k: np.ascontiguousarray(v) for k, v in sample.items()}


# ---------------------------------------------------------------------------
# 4. Pure-NumPy CenterHead decode
#
# Reimplements mmdet3d/core/bbox/coders/centerpoint_bbox_coders.py::decode
# (lines 121-225) plus the per-task offset and sigmoid/exp applied by
# get_bboxes (centerpoint.py:672, 678). The exported ONNX outputs raw logits
# for heatmap and log-space dims.
# ---------------------------------------------------------------------------
def _sigmoid(x: np.ndarray) -> np.ndarray:
    # Clamp to avoid FP32 overflow in exp(-x) for very negative logits.
    return 1.0 / (1.0 + np.exp(-np.clip(x, -80.0, 80.0)))


def _topk_2d(scores_flat: np.ndarray, K: int) -> Tuple[np.ndarray, np.ndarray]:
    """Return top-K values and their flat indices for a 1-D array."""
    if K >= scores_flat.shape[0]:
        part = np.argsort(-scores_flat)
        return scores_flat[part], part
    part = np.argpartition(-scores_flat, K - 1)[:K]
    ordered = part[np.argsort(-scores_flat[part])]
    return scores_flat[ordered], ordered


def decode_task(
    outputs: Dict[str, np.ndarray], task_id: int, params: DecodeParams,
) -> Dict[str, np.ndarray]:
    """Decode one task's 6 heads into boxes / scores / labels.

    All inputs have shape [1, C, H, W] with H=W=128. Returns up to
    `params.max_num` proposals filtered by `params.post_center_range` +
    `params.score_threshold`. The class label is shifted by
    `params.task_class_offsets[task_id]` so the two tasks share a global
    label space.
    """
    p = f"task{task_id}_"
    heat = _sigmoid(outputs[p + "heatmap"])          # [1, C, H, W]
    reg = outputs[p + "reg"]                         # [1, 2, H, W]
    hei = outputs[p + "height"]                      # [1, 1, H, W]
    dim = np.exp(outputs[p + "dim"])                 # [1, 3, H, W]
    rot = outputs[p + "rot"]                         # [1, 2, H, W]
    vel = outputs.get(p + "vel")                     # [1, 2, H, W] or None

    _, C, H, W = heat.shape
    scores_cls = heat[0].reshape(C, -1)              # [C, H*W]
    # Per-class top-K, then merge across classes (matches torch._topk logic).
    K = params.max_num
    topk_scores = np.empty((C, K), dtype=np.float32)
    topk_inds = np.empty((C, K), dtype=np.int64)
    for c in range(C):
        s, i = _topk_2d(scores_cls[c], K)
        topk_scores[c] = s
        topk_inds[c] = i
    flat = topk_scores.reshape(-1)
    s2, i2 = _topk_2d(flat, K)
    cls_idx = (i2 // K).astype(np.int64)
    within = (i2 % K).astype(np.int64)
    sel_inds = topk_inds[cls_idx, within]            # [K] — indices into H*W
    scores = s2                                      # [K]
    labels = cls_idx + params.task_class_offsets[task_id]  # [K], global class

    ys_int = (sel_inds // W).astype(np.float32)
    xs_int = (sel_inds % W).astype(np.float32)
    # WARNING: the upstream coder's _topk swaps the x/y meaning (see
    # centerpoint_bbox_coders.py lines 87-90). We follow that convention:
    # the "xs" in the decode equation is what index // W yields.
    xs_int, ys_int = ys_int, xs_int  # keep parity with torch version

    # Gather per-index regressions.
    def gather(x: np.ndarray) -> np.ndarray:
        # x: [1, D, H, W] -> [D, K]
        D = x.shape[1]
        return x[0].reshape(D, -1)[:, sel_inds]

    reg_xy = gather(reg)           # [2, K]
    hei_k = gather(hei)[0]         # [K]
    dim_k = gather(dim)            # [3, K]
    rot_k = gather(rot)            # [2, K] — (sin, cos)
    xs = xs_int + reg_xy[0]
    ys = ys_int + reg_xy[1]
    rot_ang = np.arctan2(rot_k[0], rot_k[1])

    # Feature-map xy -> ego BEV xy
    xs = xs * params.out_size_factor * params.voxel_size[0] + params.pc_range[0]
    ys = ys * params.out_size_factor * params.voxel_size[1] + params.pc_range[1]

    if vel is None:
        boxes = np.stack([xs, ys, hei_k, dim_k[0], dim_k[1], dim_k[2], rot_ang], axis=1)
    else:
        vel_k = gather(vel)
        boxes = np.stack(
            [xs, ys, hei_k, dim_k[0], dim_k[1], dim_k[2], rot_ang, vel_k[0], vel_k[1]],
            axis=1,
        )

    # Filter by post_center_range + score_threshold.
    mask = (
        (boxes[:, :3] >= params.post_center_range[:3]).all(axis=1)
        & (boxes[:, :3] <= params.post_center_range[3:]).all(axis=1)
        & (scores > params.score_threshold)
    )
    return dict(boxes=boxes[mask], scores=scores[mask], labels=labels[mask])


def decode_all(
    outputs: Dict[str, np.ndarray], params: DecodeParams,
) -> Dict[str, np.ndarray]:
    """Concatenate both tasks' decoded boxes into a single set."""
    r0 = decode_task(outputs, 0, params)
    r1 = decode_task(outputs, 1, params)
    return dict(
        boxes=np.concatenate([r0["boxes"], r1["boxes"]], axis=0),
        scores=np.concatenate([r0["scores"], r1["scores"]], axis=0),
        labels=np.concatenate([r0["labels"], r1["labels"]], axis=0),
    )


# ---------------------------------------------------------------------------
# 5. Self-distillation metric: INT8 decode vs FP32 decode.
#    Per-frame recall at BEV-center distance <= r with class match, averaged.
# ---------------------------------------------------------------------------
MATCH_RADIUS_M = 1.0  # box center distance in meters (BEV) to count as recalled


def compute_recall_vs_pseudo_gt(
    pred: Dict[str, np.ndarray], gt: Dict[str, np.ndarray]
) -> float:
    """Return the fraction of pseudo-GT boxes that have a same-class prediction
    within MATCH_RADIUS_M on the BEV plane. 1.0 means perfect match to FP32."""
    if gt["boxes"].shape[0] == 0:
        return 1.0 if pred["boxes"].shape[0] == 0 else 0.0
    if pred["boxes"].shape[0] == 0:
        return 0.0

    pred_xy = pred["boxes"][:, :2]      # [P, 2]
    gt_xy = gt["boxes"][:, :2]          # [G, 2]
    # squared L2 distances [G, P]
    dsq = ((gt_xy[:, None, :] - pred_xy[None, :, :]) ** 2).sum(axis=2)
    class_match = gt["labels"][:, None] == pred["labels"][None, :]
    dsq = np.where(class_match, dsq, np.inf)
    nearest = dsq.min(axis=1)
    return float((nearest <= MATCH_RADIUS_M ** 2).mean())


def validation_fn(
    compiled_model: ov.CompiledModel,
    validation_loader,
    pseudo_gts: List[Dict[str, np.ndarray]],
    params: DecodeParams,
) -> Tuple[float, List[float]]:
    """NNCF signature: validation_fn(compiled_model, iterable) -> (metric, per_sample).

    NNCF hands us an already-iterable sequence of model-ready dicts (the result of
    applying `transform_fn` to each dataset entry), not the `nncf.Dataset` itself.
    """
    per_sample = []
    for i, sample in enumerate(validation_loader):
        raw = _infer_fresh(compiled_model, sample)
        pred = decode_all(raw, params)
        per_sample.append(compute_recall_vs_pseudo_gt(pred, pseudo_gts[i]))
    score = float(np.mean(per_sample)) if per_sample else 0.0
    return score, per_sample


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------
def _resolve_runtime_paths(args) -> Dict[str, str]:
    """Resolve all runtime paths from CLI args.

    Keeping this centralized allows easy dataset switching (e.g., KITTI)
    without editing constants or overwriting shared artifacts.
    """
    calib_dir = os.path.abspath(args.calib_dir)
    geo_dir = os.path.abspath(args.geo_dir)
    model_fp32 = os.path.abspath(args.model_fp32)
    output = os.path.abspath(args.output)
    pseudo_gt_cache = (
        os.path.abspath(args.pseudo_gt_cache)
        if args.pseudo_gt_cache
        else os.path.join(calib_dir, "_pseudo_gt.npz")
    )
    return {
        "calib_dir": calib_dir,
        "geo_dir": geo_dir,
        "model_fp32": model_fp32,
        "output": output,
        "pseudo_gt_cache": pseudo_gt_cache,
    }


def save_pseudo_gts(gts: List[Dict[str, np.ndarray]], frame_ids: List[str], path: str) -> None:
    """Store the per-frame decoded FP32 boxes as a compressed .npz cache."""
    blob = {"frame_ids": np.array(frame_ids)}
    for i, g in enumerate(gts):
        blob[f"boxes_{i}"] = g["boxes"]
        blob[f"scores_{i}"] = g["scores"]
        blob[f"labels_{i}"] = g["labels"]
    np.savez_compressed(path, **blob)


def load_pseudo_gts(path: str, frame_ids: List[str]) -> List[Dict[str, np.ndarray]]:
    data = np.load(path, allow_pickle=False)
    saved = list(data["frame_ids"])
    if saved != frame_ids:
        raise RuntimeError(
            f"pseudo-GT cache mismatches current val split:\n"
            f"  cached: {saved[:5]}...({len(saved)})\n"
            f"  wanted: {frame_ids[:5]}...({len(frame_ids)})\n"
            f"Delete {path} and rerun with --compute-pseudo-gt."
        )
    return [
        dict(
            boxes=data[f"boxes_{i}"],
            scores=data[f"scores_{i}"],
            labels=data[f"labels_{i}"],
        )
        for i in range(len(saved))
    ]


def _infer_fresh(compiled: ov.CompiledModel, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Run one inference via a fresh infer_request.

    The Arc B580 OpenCL driver leaks resources if the same shared infer_request
    is reused across many calls (symptom: CL_OUT_OF_RESOURCES around ~20 calls,
    and cross-process contamination). `infer_new_request` allocates a fresh
    request each call — this is the pattern bevfusion_standalone_ov_inference_dump.py
    uses for the same graph.
    """
    outs = compiled.infer_new_request(inputs)
    return {list(k.names)[0]: v for k, v in outs.items()}


def compute_pseudo_gts(
    core: ov.Core, model: ov.Model, val_set: UnifiedDataset, device: str,
    params: DecodeParams,
) -> List[Dict[str, np.ndarray]]:
    compiled = core.compile_model(model, device_name=device)
    gts = []
    for i, fid in enumerate(val_set.frame_ids):
        sample = val_set[fid]
        raw = _infer_fresh(compiled, transform_fn(sample))
        gt = decode_all(raw, params)
        gts.append(gt)
        if (i + 1) % 20 == 0 or i + 1 == len(val_set.frame_ids):
            print(f"  [fp32 pseudo-GT] {i+1}/{len(val_set.frame_ids)}  "
                  f"{fid}: {gt['boxes'].shape[0]} boxes")
    return gts


def split_frames(all_fids: List[str], n_calib: int, n_val: int) -> Tuple[List[str], List[str]]:
    assert n_calib + n_val <= len(all_fids), (
        f"need {n_calib+n_val} frames, only {len(all_fids)} dumped"
    )
    return all_fids[:n_calib], all_fids[n_calib : n_calib + n_val]


def run_pseudo_gt_chunk(args) -> None:
    """Internal stage: process a slice of frame IDs and write a partial .npz.

    The Arc B580 GPU driver leaks OpenCL resources across many infer_request
    calls (CL_OUT_OF_RESOURCES around frame ~20). Launching a fresh subprocess
    per chunk is the cleanest workaround — each child compiles once, processes
    CHUNK frames, dumps a partial cache, and exits to reclaim the GPU context.
    """
    chunk_fids = args.chunk_fids.split(",")
    print(f"[pseudo-gt-chunk] {len(chunk_fids)} frames on {args.device}: "
          f"{chunk_fids[0]}..{chunk_fids[-1]}")
    paths = _resolve_runtime_paths(args)
    params = _build_decode_params(args)
    val_set = UnifiedDataset(chunk_fids, paths["calib_dir"], paths["geo_dir"])
    core = ov.Core()
    fp32 = core.read_model(paths["model_fp32"])
    t0 = time.time()
    gts = compute_pseudo_gts(core, fp32, val_set, args.device, params)
    print(f"[pseudo-gt-chunk] decoded in {time.time()-t0:.1f}s; "
          f"writing {args.chunk_output}")
    save_pseudo_gts(gts, chunk_fids, args.chunk_output)


def run_compute_pseudo_gt(args) -> None:
    """Subcommand: produce the FP32 reference cache for all val frames.

    Fans out into subprocess chunks of ``args.chunk_size`` frames (default 16)
    to avoid a GPU driver resource leak observed on Arc B580 after ~20 infers.
    Each chunk writes a partial .npz; this function then stitches them into
    the canonical PSEUDO_GT_CACHE and cleans up.
    """
    import subprocess
    import tempfile

    paths = _resolve_runtime_paths(args)
    all_fids = discover_frames(paths["calib_dir"])
    _, val_fids = split_frames(all_fids, args.n_calib, args.n_val)

    chunk_size = args.chunk_size
    tmp_dir = tempfile.mkdtemp(
        prefix="pseudo_gt_chunks_", dir=os.path.dirname(paths["pseudo_gt_cache"])
    )
    chunk_outputs = []
    print(f"[pseudo-GT] fanning out {len(val_fids)} frames "
          f"into chunks of {chunk_size} (tmp={tmp_dir})")

    t_total = time.time()
    cooldown = float(os.environ.get("GPU_CHUNK_COOLDOWN_S", "3"))
    max_retries = int(os.environ.get("GPU_CHUNK_RETRIES", "2"))
    n_chunks = (len(val_fids) + chunk_size - 1) // chunk_size
    for start in range(0, len(val_fids), chunk_size):
        chunk = val_fids[start : start + chunk_size]
        idx = start // chunk_size
        out_path = os.path.join(tmp_dir, f"chunk_{idx:03d}.npz")
        chunk_outputs.append((chunk, out_path))
        cmd = [
            sys.executable, "-u", __file__,
            "--stage", "pseudo-gt-chunk",
            "--device", args.device,
            "--calib-dir", paths["calib_dir"],
            "--geo-dir", paths["geo_dir"],
            "--model-fp32", paths["model_fp32"],
            "--output", paths["output"],
            "--pseudo-gt-cache", paths["pseudo_gt_cache"],
            "--chunk-fids", ",".join(chunk),
            "--chunk-output", out_path,
        ]
        if args.config:
            cmd.extend(["--config", args.config])
        print(f"  chunk {idx+1}/{n_chunks}: frames {chunk[0]}..{chunk[-1]} ({len(chunk)})")
        for attempt in range(1, max_retries + 2):
            if idx > 0 or attempt > 1:
                time.sleep(cooldown)
            t0 = time.time()
            rc = subprocess.call(cmd)
            if rc == 0 and os.path.exists(out_path):
                print(f"    ok in {time.time()-t0:.1f}s (attempt {attempt})")
                break
            print(f"    attempt {attempt} failed (rc={rc}), retry after {cooldown:.1f}s cooldown")
        else:
            raise SystemExit(
                f"pseudo-GT chunk {idx} failed after {max_retries+1} attempts"
            )

    # Merge chunks into one cache.
    print(f"[pseudo-GT] merging {len(chunk_outputs)} chunks")
    all_gts: List[Dict[str, np.ndarray]] = []
    all_ids: List[str] = []
    for chunk, path in chunk_outputs:
        all_gts.extend(load_pseudo_gts(path, chunk))
        all_ids.extend(chunk)
    save_pseudo_gts(all_gts, all_ids, paths["pseudo_gt_cache"])
    for _, path in chunk_outputs:
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass
    print(f"[pseudo-GT] wrote {paths['pseudo_gt_cache']} "
          f"({len(all_ids)} frames, total {time.time()-t_total:.1f}s)")


def run_quantize(args) -> None:
    """Subcommand: run NNCF. Expects pseudo-GT cache to exist already."""
    paths = _resolve_runtime_paths(args)
    params = _build_decode_params(args)
    all_fids = discover_frames(paths["calib_dir"])
    calib_fids, val_fids = split_frames(all_fids, args.n_calib, args.n_val)
    print(f"  calib: {len(calib_fids)}   val: {len(val_fids)}")

    calib_set = UnifiedDataset(calib_fids, paths["calib_dir"], paths["geo_dir"])
    val_set = UnifiedDataset(val_fids, paths["calib_dir"], paths["geo_dir"])

    if not os.path.exists(paths["pseudo_gt_cache"]):
        raise SystemExit(
            f"pseudo-GT cache missing: {paths['pseudo_gt_cache']}\n"
            f"run with --stage pseudo-gt first."
        )
    pseudo_gts = load_pseudo_gts(paths["pseudo_gt_cache"], val_fids)
    gt_counts = [g["boxes"].shape[0] for g in pseudo_gts]
    print(f"  pseudo-GT box counts: mean={np.mean(gt_counts):.1f}  "
          f"min={min(gt_counts)}  max={max(gt_counts)}")

    core = ov.Core()
    fp32_model = core.read_model(paths["model_fp32"])

    calib_list = list(calib_set)
    val_list = list(val_set)
    calib_nncf = nncf.Dataset(calib_list, transform_fn)
    val_nncf = nncf.Dataset(val_list, transform_fn)
    val_fn = partial(validation_fn, pseudo_gts=pseudo_gts, params=params)

    preset_map = {
        "performance": nncf.QuantizationPreset.PERFORMANCE,
        "mixed": nncf.QuantizationPreset.MIXED,
    }
    preset = preset_map[args.preset.lower()]

    # Optionally extend IgnoredScope with more node names / patterns.
    extra_names = [n.strip() for n in args.extra_ignored_names.split(",") if n.strip()]
    extra_patterns = [p.strip() for p in args.extra_ignored_patterns.split(",") if p.strip()]
    ignored = IGNORED_SCOPE
    if extra_names or extra_patterns:
        ignored = nncf.IgnoredScope(
            names=IGNORED_SCOPE.names + extra_names,
            types=IGNORED_SCOPE.types,
            patterns=extra_patterns,
        )

    # Activation range estimator — for BEVFusion the post/ subgraph has very
    # heavy-tailed activations (cam_bev min/max ±1500 but p99=0.15;
    # task0_heatmap min=-150 max=28 but p99=-13). Raw MINMAX calibration
    # allocates 99.9% of the INT8 range to outliers and erases the real
    # signal. Use percentile-based range estimators to clip the tails.
    from nncf.quantization.range_estimator import (
        RangeEstimatorParametersSet, RangeEstimatorParameters,
        StatisticsCollectorParameters, StatisticsType, AggregatorType,
    )
    range_preset_map = {
        "minmax": RangeEstimatorParametersSet.MINMAX,
        "mean_minmax": RangeEstimatorParametersSet.MEAN_MINMAX,
        "median_minmax": RangeEstimatorParametersSet.MEDIAN_MINMAX,
        "mean_no_outliers": RangeEstimatorParametersSet.MEAN_NO_OUTLIERS_MINMAX,
        "mean_quantile": RangeEstimatorParametersSet.MEAN_QUANTILE,
        "histogram": RangeEstimatorParametersSet.HISTOGRAM,
    }
    act_range = range_preset_map[args.activation_range.lower()]
    if args.quantile_outlier_prob is not None:
        # Deep copy the preset and override the quantile probability.
        act_range = RangeEstimatorParameters(
            min=StatisticsCollectorParameters(
                statistics_type=act_range.min.statistics_type,
                aggregator_type=act_range.min.aggregator_type,
                clipping_value=act_range.min.clipping_value,
                quantile_outlier_prob=args.quantile_outlier_prob,
            ),
            max=StatisticsCollectorParameters(
                statistics_type=act_range.max.statistics_type,
                aggregator_type=act_range.max.aggregator_type,
                clipping_value=act_range.max.clipping_value,
                quantile_outlier_prob=args.quantile_outlier_prob,
            ),
        )

    advanced = nncf.AdvancedQuantizationParameters(
        activations_range_estimator_params=act_range,
    )

    print(f"[quantize] preset={preset.value}  ignored_names={len(ignored.names)}  "
          f"ignored_patterns={len(ignored.patterns) if ignored.patterns else 0}  "
          f"act_range={args.activation_range}")

    t0 = time.time()
    if args.plain_ptq:
        print("[quantize] nncf.quantize (plain PTQ, no accuracy rollback) ...")
        quantized = nncf.quantize(
            fp32_model,
            calibration_dataset=calib_nncf,
            preset=preset,
            target_device=nncf.TargetDevice.GPU,
            fast_bias_correction=False,
            ignored_scope=ignored,
            advanced_parameters=advanced,
        )
    else:
        print(f"[quantize] nncf.quantize_with_accuracy_control "
              f"(max_drop={args.max_drop}, drop_type=ABSOLUTE) ...")
        # Serial ranking: B580 OpenCL driver cannot tolerate two concurrent
        # infer_requests on a graph with SparseConvolution. Force 1 worker.
        advanced_restorer = nncf.AdvancedAccuracyRestorerParameters(
            num_ranking_workers=1,
            ranking_subset_size=min(args.ranking_subset_size, len(val_list)),
            max_num_iterations=args.max_restore_iters,
        )
        quantized = nncf.quantize_with_accuracy_control(
            fp32_model,
            calibration_dataset=calib_nncf,
            validation_dataset=val_nncf,
            validation_fn=val_fn,
            max_drop=args.max_drop,
            drop_type=nncf.DropType.ABSOLUTE,
            preset=preset,
            target_device=nncf.TargetDevice.GPU,
            fast_bias_correction=False,
            ignored_scope=ignored,
            advanced_quantization_parameters=advanced,
            advanced_accuracy_restorer_parameters=advanced_restorer,
        )
    print(f"[quantize] done in {time.time()-t0:.1f}s; saving to {paths['output']}")
    os.makedirs(os.path.dirname(paths["output"]), exist_ok=True)
    ov.save_model(quantized, paths["output"])

    # In-memory verification against the just-quantized Model object. With the
    # OV 2026.1 opset15 patch (BevPoolV2 / SparseConvolution / SparseToDense
    # registered in opset15_tbl.hpp + opset.cpp), the saved .xml can also be
    # re-read now via core.read_model; we still use the in-memory object here
    # to avoid an unnecessary disk round-trip.
    print("\n[verify] FP32 vs INT8 head-output comparison on val frames")
    core = ov.Core()
    fp32_compiled = core.compile_model(fp32_model, device_name=args.device)
    int8_compiled = core.compile_model(quantized, device_name=args.device)

    n_verify = min(10, len(val_list))
    int8_per_sample = []
    for i in range(n_verify):
        inputs = transform_fn(val_list[i])
        r_fp = _infer_fresh(fp32_compiled, inputs)
        r_q = _infer_fresh(int8_compiled, inputs)
        h1 = r_fp["task0_heatmap"]
        h2 = r_q["task0_heatmap"]
        l1 = float(np.abs(h1 - h2).mean())
        pred = decode_all(r_q, params)
        recall = compute_recall_vs_pseudo_gt(pred, pseudo_gts[i])
        int8_per_sample.append(recall)
        print(f"  {val_fids[i]:>6}  task0_heatmap L1={l1:.4f}  "
              f"FP32_boxes={pseudo_gts[i]['boxes'].shape[0]:3d}  "
              f"INT8_boxes={pred['boxes'].shape[0]:3d}  recall={recall:.3f}")
    print(f"[verify] mean recall over {n_verify} frames: "
          f"{np.mean(int8_per_sample):.4f}  (1.0 = INT8 covers FP32)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage",
                    choices=["pseudo-gt", "pseudo-gt-chunk", "quantize", "all"],
                    default="all",
                    help="pseudo-gt: produce the FP32 reference cache via subprocess chunks. "
                         "pseudo-gt-chunk: internal — process one chunk (called by pseudo-gt). "
                         "quantize: run NNCF using cached pseudo-GT. "
                         "all: pseudo-gt then quantize.")
    ap.add_argument("--smoke", action="store_true",
                    help="3 calib / 2 val frames, max_drop=1.0 (effectively no rollback)")
    ap.add_argument("--config", default="",
                    help="path to dataset config (e.g. configs/Kitti/det/centerhead/"
                         "secfpn/camera+lidar/default.yaml). When given, "
                         "pc_range / post_center_range / voxel_size / out_size_factor / "
                         "score_threshold / max_num and per-task class offsets are "
                         "read from cfg.model.heads.object.bbox_coder + .tasks. "
                         "Default (empty) keeps the legacy V2X-I hard-coded values "
                         "for back-compat. KITTI runs MUST pass --config.")
    ap.add_argument("--n-calib", type=int, default=300)
    ap.add_argument("--n-val", type=int, default=100)
    ap.add_argument("--max-drop", type=float, default=0.05)
    ap.add_argument("--device", default=DEVICE)
    ap.add_argument("--model-fp32", default=DEFAULT_MODEL_FP32,
                    help="path to the FP32 unified ONNX used for pseudo-GT and PTQ")
    ap.add_argument("--output", default=DEFAULT_MODEL_INT8,
                    help="path to output INT8 IR (.xml)")
    ap.add_argument("--geo-dir", default=DEFAULT_GEO_DIR,
                    help="directory containing indices.bin and intervals.bin")
    ap.add_argument("--calib-dir", default=DEFAULT_CALIB_DIR,
                    help="directory containing dumped calibration npy files")
    ap.add_argument("--pseudo-gt-cache", default="",
                    help="path to pseudo-GT cache .npz; default is <calib-dir>/_pseudo_gt.npz")
    ap.add_argument("--chunk-size", type=int, default=100,
                    help="pseudo-GT frames per GPU-process chunk. With infer_new_request "
                         "the B580 is fine even at 100+ frames per process.")
    ap.add_argument("--ranking-subset-size", type=int, default=30,
                    help="frames used to rank each rollback candidate during accuracy "
                         "restoration. NNCF default is 300; smaller = faster with less "
                         "stable rankings.")
    ap.add_argument("--max-restore-iters", type=int, default=32,
                    help="hard cap on accuracy-restoration iterations.")
    ap.add_argument("--plain-ptq", action="store_true",
                    help="skip quantize_with_accuracy_control and run plain "
                         "nncf.quantize only. Faster and avoids the B580 driver's "
                         "inability to tolerate ~100 sequential GPU compiles.")
    ap.add_argument("--preset", choices=["performance", "mixed"], default="performance",
                    help="performance = symmetric activations (faster); "
                         "mixed = asymmetric activations, usually better for "
                         "image-feature networks like the camera backbone.")
    ap.add_argument("--extra-ignored-names", default="",
                    help="comma-separated node names to add to IgnoredScope.names. "
                         "Use to exclude e.g. depthnet / ResNet stem convs if PTQ "
                         "loses too much accuracy there.")
    ap.add_argument("--extra-ignored-patterns", default="",
                    help="comma-separated regex patterns for IgnoredScope.patterns.")
    ap.add_argument("--activation-range",
                    choices=["minmax", "mean_minmax", "median_minmax",
                             "mean_no_outliers", "mean_quantile", "histogram"],
                    default="histogram",
                    help="activation range estimator. Default=histogram because "
                         "BEVFusion's post/ decoder has heavy-tailed activations "
                         "(cam_bev ±1500 with p99=0.15, task0_heatmap min=-150 "
                         "max=28 with p99=-13). Raw minmax wastes the INT8 range "
                         "on outliers and collapses all signal; histogram finds "
                         "MSE-minimizing bounds from the value distribution and "
                         "keeps recall ~0.91 while quantizing the full post/ "
                         "subgraph (vs 0.004 with minmax + full quantize).")
    ap.add_argument("--quantile-outlier-prob", type=float, default=None,
                    help="only used with mean_no_outliers/mean_quantile; overrides "
                         "the default 1e-4. Larger = clip more outliers.")
    # Internal-only args for the chunk subprocess.
    ap.add_argument("--chunk-fids", default="", help=argparse.SUPPRESS)
    ap.add_argument("--chunk-output", default="", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.smoke:
        args.n_calib, args.n_val, args.max_drop = 3, 2, 1.0
        args.chunk_size = 2  # trivial smoke size

    print(f"OV: {ov.get_version()}")
    print(f"NNCF: {nncf.__version__}")
    print(f"Device: {args.device}   stage: {args.stage}")

    if args.stage == "pseudo-gt":
        run_compute_pseudo_gt(args)
    elif args.stage == "pseudo-gt-chunk":
        run_pseudo_gt_chunk(args)
    elif args.stage == "quantize":
        run_quantize(args)
    else:
        run_compute_pseudo_gt(args)
        run_quantize(args)


if __name__ == "__main__":
    main()
