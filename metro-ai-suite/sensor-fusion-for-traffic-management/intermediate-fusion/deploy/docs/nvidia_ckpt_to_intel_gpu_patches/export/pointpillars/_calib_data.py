"""Shared calibration helpers for INT8 quantization of the 4 PointPillars ONNX.

The four quantize_*.py scripts each need a different set of tensors:

    camera.backbone.onnx    input: img  [1, 3, 864, 1536]
    lidar_pfe.onnx          input: features [V|V_max, 100, 4]
                                    num_voxels [V|V_max]
                                    coors [V|V_max, 4]
    fuser.onnx              input: cam_bev  [1, 80, 128, 128]
                                    lidar_bev [1, 64, 128, 128]
    head.onnx               input: fused_bev [1, 80, 128, 128]

Instead of chaining compiled OV models together (as v2xfusionDev does — fragile
and slow), we load the PyTorch model once and run its real forward to get all
the intermediate BEV tensors we need. Each script picks the tensors it wants.

Public API:
    build_pt_model(config_path, ckpt_path)
    calib_samples(cfg, num_samples) -> iterator of mmdet3d data dicts
    pt_extract_all(model, data_dict, fixed_V=None) -> dict with:
        img_nchw:   np [1, 3, H, W]  f32
        features:   np [V|V_max, N, C]  f32
        num_voxels: np [V|V_max]     i32
        coors:      np [V|V_max, 4]  i32  (batch=0, x, y, z)
        cam_bev:    np [1, 80, 128, 128] f32
        lidar_bev:  np [1, 64, 128, 128] f32  (scatter output)
        fused_bev:  np [1, 80, 128, 128] f32  (fuser output)
"""

from __future__ import annotations

import os
import sys
from functools import partial
from typing import Iterator, Optional

import numpy as np
import torch
import torch.nn.functional as F

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def build_pt_model(config_path: str, ckpt_path: str):
    """Load the PointPillars BEVFusion model in eval mode on CUDA."""
    from torchpack.utils.config import configs
    from mmcv import Config
    from mmdet3d.models import build_model
    from mmdet3d.utils import recursive_eval

    configs.load(config_path, recursive=True)
    cfg = Config(recursive_eval(configs), filename=config_path)
    cfg.model.train_cfg = None
    model = build_model(cfg.model, test_cfg=cfg.get("test_cfg"))
    ckpt = torch.load(ckpt_path, map_location="cpu")
    model.load_state_dict(ckpt["state_dict"], strict=False)
    return model.cuda().eval(), cfg


def calib_samples(cfg, num_samples: int, split: str = "val") -> Iterator[dict]:
    """Yield real mmdet3d-format data dicts from the specified split.

    Each dict has keys: img / points / camera2ego / lidar2ego / lidar2camera /
    lidar2image / camera_intrinsics / camera2lidar / img_aug_matrix /
    lidar_aug_matrix / metas / denorms etc.
    """
    from mmdet3d.datasets import build_dataloader, build_dataset
    from mmdet3d.datasets.v2x_dataset import collate_fn

    dataset = build_dataset(cfg.data[split])
    dataloader = build_dataloader(
        dataset, samples_per_gpu=1,
        workers_per_gpu=cfg.data.workers_per_gpu, dist=False, shuffle=False,
    )
    dataloader.collate_fn = partial(collate_fn, is_return_depth=False)
    for i, data in enumerate(dataloader):
        if i >= num_samples:
            break
        yield data


def _pad_first_dim(t: torch.Tensor, V_fix: int) -> torch.Tensor:
    """Zero-pad along dim 0 to V_fix; truncate if longer."""
    if t.shape[0] >= V_fix:
        return t[:V_fix].contiguous()
    pad = torch.zeros((V_fix - t.shape[0],) + tuple(t.shape[1:]),
                      dtype=t.dtype, device=t.device)
    return torch.cat([t, pad], dim=0)


def _pfe_export_forward(pfe_module, features, num_voxels, coors):
    """Replicates the PillarFeatureNet export-path forward (see export-lidar.py).

    We mirror the wrapper so calibration-time `lidar_bev` matches what the
    deployed ONNX produces. Numerically close to `PillarFeatureNet.forward`
    with BN folded into Linear.
    """
    dtype = features.dtype
    one_f = torch.ones_like(num_voxels, dtype=dtype)
    denom = torch.max(num_voxels.type_as(features), one_f).view(-1, 1, 1)
    points_mean = features[:, :, :3].sum(dim=1, keepdim=True) / denom
    f_cluster = features[:, :, :3] - points_mean

    f_center = torch.zeros_like(features[:, :, :2])
    f_center[:, :, 0] = features[:, :, 0] - (
        coors[:, 1].to(dtype).unsqueeze(1) * pfe_module.vx + pfe_module.x_offset
    )
    f_center[:, :, 1] = features[:, :, 1] - (
        coors[:, 2].to(dtype).unsqueeze(1) * pfe_module.vy + pfe_module.y_offset
    )

    decorated = torch.cat([features, f_cluster, f_center], dim=-1)
    voxel_count = decorated.shape[1]
    max_num = torch.arange(voxel_count, dtype=torch.int32,
                           device=decorated.device).view(1, -1)
    mask = num_voxels.to(torch.int32).unsqueeze(-1) > max_num
    mask = mask.unsqueeze(-1).type_as(decorated)
    decorated = decorated * mask

    x = decorated
    for pfn in pfe_module.pfn_layers:
        x = pfn(x, export=True)
    return x.squeeze(1)  # [V, 64]


def _as_tensor(v):
    """Extract a torch.Tensor from an mmdet3d DataContainer or pass-through."""
    if hasattr(v, "data"):
        d = v.data
        if isinstance(d, torch.Tensor):
            return d
        if isinstance(d, (list, tuple)) and len(d) > 0 and isinstance(d[0], torch.Tensor):
            return d[0]
        # metas / points: caller handles those specially.
        return d
    return v


def _as_meta(v):
    """Extract the metas list (items may be dicts)."""
    if hasattr(v, "data"):
        d = v.data
        # data might be a list already, or a list-of-lists from distributed collate
        while isinstance(d, list) and len(d) == 1 and isinstance(d[0], list):
            d = d[0]
        return d
    if isinstance(v, list):
        return v
    return [v]


def pt_extract_all(model, data: dict, fixed_V: Optional[int] = None) -> dict:
    """Run every stage of the model once, collect intermediate tensors as numpy.

    Robust to both train-split collate (DataContainer.data) and val-split
    collate (raw Tensor).
    """
    with torch.no_grad():
        # ----- Camera input -----
        img = _as_tensor(data["img"]).cuda()  # [1, 1, 3, H, W] or [1, 3, H, W]
        if img.dim() == 4:
            img = img.unsqueeze(0)
        B, N, C, H, W = img.shape
        assert B == 1 and N == 1, f"expected B=N=1, got {(B, N)}"
        img_nchw = img.view(B * N, C, H, W)  # [1, 3, H, W]

        # ----- Points -----
        pts_v = data["points"]
        if hasattr(pts_v, "data"):
            pts_d = pts_v.data
            while isinstance(pts_d, list) and len(pts_d) > 0 and isinstance(pts_d[0], list):
                pts_d = pts_d[0]
            pts = pts_d[0].cuda() if isinstance(pts_d, list) else pts_d.cuda()
        else:
            # val collate: direct list of tensors
            pts_d = pts_v
            while isinstance(pts_d, list) and len(pts_d) > 0 and isinstance(pts_d[0], list):
                pts_d = pts_d[0]
            pts = pts_d[0].cuda() if isinstance(pts_d, list) else pts_d.cuda()

        # ----- Voxelization -----
        feats, coors, sizes = model.voxelize([pts])
        feats = feats.contiguous()
        sizes = sizes.int()
        coors = coors.int()
        if fixed_V is not None:
            feats = _pad_first_dim(feats, fixed_V)
            sizes = _pad_first_dim(sizes, fixed_V)
            coors = _pad_first_dim(coors, fixed_V)

        # ----- Lidar PFE -----
        pfe = model.encoders["lidar"]["backbone"].pts_voxel_encoder
        pillar_features = _pfe_export_forward(pfe, feats, sizes, coors)  # [V, 64]
        scatter = model.encoders["lidar"]["backbone"].pts_middle_encoder
        lidar_bev = scatter(pillar_features, coors, batch_size=1)  # [1, 64, 128, 128]

        # ----- Camera BEV (full LSSV2XTransform path) -----
        cam_bev = model.extract_camera_features(
            img,
            [pts],
            _as_tensor(data["camera2ego"]).cuda(),
            _as_tensor(data["lidar2ego"]).cuda(),
            _as_tensor(data["lidar2camera"]).cuda(),
            _as_tensor(data["lidar2image"]).cuda(),
            _as_tensor(data["camera_intrinsics"]).cuda(),
            _as_tensor(data["camera2lidar"]).cuda(),
            _as_tensor(data["img_aug_matrix"]).cuda(),
            _as_tensor(data["lidar_aug_matrix"]).cuda(),
            _as_meta(data["metas"]),
            denorms=_as_tensor(data["denorms"]).cuda(),
        )  # [1, 80, 128, 128]

        # ----- Fuser + Decoder (matches export-fuser.py's new split in §37) -----
        fused_bev = model.fuser([cam_bev, lidar_bev])        # [1, 80, 128, 128]
        decoder_out = model.decoder["backbone"](fused_bev)
        decoder_out = model.decoder["neck"](decoder_out)
        if isinstance(decoder_out, (list, tuple)):
            decoder_out = decoder_out[0]                      # [1, 256, 128, 128]

    def to_np(t, dtype=np.float32):
        arr = t.detach().cpu().numpy()
        if arr.dtype != dtype:
            arr = arr.astype(dtype)
        return np.ascontiguousarray(arr)

    return {
        "img_nchw":    to_np(img_nchw, np.float32),
        "features":    to_np(feats,    np.float32),
        "num_voxels":  to_np(sizes,    np.int32),
        "coors":       to_np(coors,    np.int32),
        "cam_bev":     to_np(cam_bev,  np.float32),
        "lidar_bev":   to_np(lidar_bev,np.float32),
        "fused_bev":   to_np(fused_bev,np.float32),     # fuser pre-decoder
        "decoder_out": to_np(decoder_out, np.float32),  # fuser post-decoder (head input)
    }
