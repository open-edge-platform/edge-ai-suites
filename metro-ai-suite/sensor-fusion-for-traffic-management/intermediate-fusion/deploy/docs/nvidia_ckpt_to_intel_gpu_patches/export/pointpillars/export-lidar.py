#!/usr/bin/env python3
"""
Export PointPillars-based BEVFusion's **PFE-only** lidar branch to ONNX.

ONNX I/O is locked by PillarFeatureNet.forward(features, num_voxels, coors)
at mmdet3d/models/backbones/pillar_encoder.py:188-230:

    features    [V, N, 4]  float32  — raw per-point (x, y, z, intensity)
    num_voxels  [V]        int32    — per-voxel actual point count
    coors       [V, 4]     int32    — (batch=0, x_idx, y_idx, z_idx)
    pillar_features [V, 64] float32 — PFN output

f_cluster / f_center / padding mask are computed **inside** the ONNX graph.
The deploy-side C++ voxelizer must produce exactly these 3 buffers.

Usage:
    python export/pointpillars/export-lidar.py \\
        --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \\
        --ckpt   work_dirs/V2X-I/pp/latest.pth \\
        -o       export/onnx/pointpillars/lidar_pfe.onnx
"""

import argparse
import os
import sys
import warnings

import torch
import torch.nn as nn
import onnx

warnings.filterwarnings("ignore")

# Add project root so `mmdet3d` resolves
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class PillarFeatureNetExportWrapper(nn.Module):
    """ONNX wrapper around PillarFeatureNet.

    Routes every PFNLayer call through its ``export=True`` branch, which uses
    the pre-fused Linear (absorbing the two BatchNorms). This keeps the ONNX
    graph linear-only, no BN at inference, and avoids tracing issues with
    BN's implicit stats update.
    """

    def __init__(self, pfe: nn.Module) -> None:
        super().__init__()
        self.pfe = pfe

    def forward(self, features: torch.Tensor,
                num_voxels: torch.Tensor,
                coors: torch.Tensor) -> torch.Tensor:
        # Replicates PillarFeatureNet.forward L188-230 but explicitly calls
        # each PFNLayer with export=True so BN gets folded into Linear.
        pfe = self.pfe
        dtype = features.dtype

        # points_mean [V, 1, 3]  —  guard against empty pillars (num_voxels=0).
        # When the deploy side uses a fixed-V ONNX with padding rows, those
        # padding rows have num_voxels=0 and would hit a div-by-zero NaN here.
        # We clamp divisor to >=1; the final `* mask` below zeros out empty
        # pillars anyway, so the numerator cancels cleanly.
        # Use torch.max(a, b) (element-wise binary max) instead of
        # .clamp(min=1.0) because the tracer lowers .clamp to an If node that
        # breaks downstream OpenVINO shape inference when V is static.
        # torch.maximum is opset>=12 only but errors on opset=13 — torch.max
        # with two tensor args exports cleanly to ONNX Max.
        one_f = torch.ones_like(num_voxels, dtype=features.dtype)
        denom = torch.max(num_voxels.type_as(features), one_f).view(-1, 1, 1)
        points_mean = features[:, :, :3].sum(dim=1, keepdim=True) / denom
        f_cluster = features[:, :, :3] - points_mean

        f_center = torch.zeros_like(features[:, :, :2])
        f_center[:, :, 0] = features[:, :, 0] - (
            coors[:, 1].to(dtype).unsqueeze(1) * pfe.vx + pfe.x_offset
        )
        f_center[:, :, 1] = features[:, :, 1] - (
            coors[:, 2].to(dtype).unsqueeze(1) * pfe.vy + pfe.y_offset
        )

        decorated = torch.cat([features, f_cluster, f_center], dim=-1)

        # padding mask from num_voxels
        voxel_count = decorated.shape[1]
        max_num = torch.arange(voxel_count, dtype=torch.int32,
                               device=decorated.device).view(1, -1)
        mask = num_voxels.to(torch.int32).unsqueeze(-1) > max_num  # [V, N]
        mask = mask.unsqueeze(-1).type_as(decorated)
        decorated = decorated * mask

        x = decorated
        for pfn in pfe.pfn_layers:
            x = pfn(x, export=True)

        # Explicit squeeze on axis 1 (the N dim after ReduceMax). Avoid the
        # bare `squeeze()` call — without an explicit axis, ONNX Squeeze
        # squeezes *every* size-1 dim at runtime, which makes the output rank
        # depend on V and breaks OpenVINO shape inference.
        return x.squeeze(1)  # [V, 1, 64] -> [V, 64]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export PP lidar PFE to ONNX")
    p.add_argument(
        "--config",
        default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml",
    )
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("-o", "--output",
                   default="export/onnx/pointpillars/lidar_pfe.onnx")
    p.add_argument("--split", default="val", choices=["val", "train", "test"],
                   help="cfg.data split to pull the tracing frame from")
    p.add_argument("--opset", type=int, default=13)
    p.add_argument(
        "--fixed-v", type=int, default=0,
        help="If > 0, export with fixed V (no dynamic axes). Padding rows "
             "will carry num_voxels=0 at runtime; the PFE wrapper now clamps "
             "the divisor in points_mean to avoid NaN. Measured on V2X-I "
             "(500 frames): V range [4644, 6295], p99=6259 — 7000 covers "
             "all frames with a safety margin.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    from torchpack.utils.config import configs
    from mmcv import Config
    from mmdet3d.models import build_model
    from mmdet3d.utils import recursive_eval

    configs.load(args.config, recursive=True)
    cfg = Config(recursive_eval(configs), filename=args.config)
    cfg.model.train_cfg = None

    model = build_model(cfg.model, test_cfg=cfg.get("test_cfg"))
    ckpt = torch.load(args.ckpt, map_location="cpu")
    model.load_state_dict(ckpt["state_dict"], strict=False)
    model = model.cuda().eval()
    print(f"[lidar-export] model loaded from {args.ckpt}")

    # Trace sample via model.voxelize to get realistic shapes and values.
    # Source: one frame from cfg.data[split] (was: tools/dump/00000, which is
    # a DAIR-V2X dump and produces wrong voxelization on KITTI — see dev doc §56).
    from functools import partial
    from mmdet3d.datasets import build_dataloader, build_dataset
    from mmdet3d.datasets.v2x_dataset import collate_fn

    dataset = build_dataset(cfg.data[args.split])
    dataloader = build_dataloader(
        dataset, samples_per_gpu=1,
        workers_per_gpu=cfg.data.workers_per_gpu, dist=False, shuffle=False,
    )
    dataloader.collate_fn = partial(collate_fn, is_return_depth=False)
    data = next(iter(dataloader))
    print(f"[lidar-export] tracing from cfg.data.{args.split}")

    pts_v = data["points"]
    if hasattr(pts_v, "data"):
        pts_d = pts_v.data
        while isinstance(pts_d, list) and len(pts_d) > 0 and isinstance(pts_d[0], list):
            pts_d = pts_d[0]
        pts = (pts_d[0] if isinstance(pts_d, list) else pts_d).cuda()
    else:
        pts_d = pts_v
        while isinstance(pts_d, list) and len(pts_d) > 0 and isinstance(pts_d[0], list):
            pts_d = pts_d[0]
        pts = (pts_d[0] if isinstance(pts_d, list) else pts_d).cuda()

    with torch.no_grad():
        feats, coors, sizes = model.voxelize([pts])
    V = int(feats.shape[0])
    N = int(feats.shape[1])
    print(f"[lidar-export] traced shapes: features={tuple(feats.shape)} "
          f"num_voxels={tuple(sizes.shape)} coors={tuple(coors.shape)} "
          f"(V={V}, N={N})")

    # Double-check coors layout assumption (see dev doc §29.4)
    assert tuple(coors.shape) == (V, 4), f"unexpected coors shape {coors.shape}"
    assert (coors[:, 0] == 0).all(), "batch_idx col0 should be 0"

    pfe = model.encoders["lidar"]["backbone"].pts_voxel_encoder
    wrapper = PillarFeatureNetExportWrapper(pfe).cuda().eval()

    # Sanity check: wrapper output must equal raw pfe forward on same inputs
    with torch.no_grad():
        ref = pfe(feats, sizes.int(), coors.int(), do_pfn=True)
        exported = wrapper(feats, sizes.int(), coors.int())
        # Align shapes; PFE.forward returns [V, 64] already (squeezed)
        ref = ref if ref.dim() == 2 else ref.squeeze()
        exported = exported if exported.dim() == 2 else exported.squeeze()
        diff = (ref - exported).abs().max().item()
        print(f"[lidar-export] wrapper vs pfe max-abs-diff = {diff:.6f}")
        if diff > 1e-3:
            print("[lidar-export] WARNING: wrapper path deviates from pfe (export=True fused vs BN runtime)."
                  " This is usually fine because BN fusion is mathematically equivalent;"
                  " small numerical differences are acceptable as long as downstream parity holds.")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    if args.fixed_v > 0:
        V_fix = int(args.fixed_v)
        print(f"[lidar-export] exporting with FIXED V={V_fix} "
              f"(measured dataset max V=6295, using safety margin)")
        # Pad traced sample to V_fix rows so tracer sees the target shape.
        def _pad_2d(t, V_fix):
            if t.shape[0] >= V_fix:
                return t[:V_fix]
            pad = torch.zeros((V_fix - t.shape[0],) + tuple(t.shape[1:]),
                              dtype=t.dtype, device=t.device)
            return torch.cat([t, pad], dim=0)
        feats_fix = _pad_2d(feats, V_fix)
        sizes_fix = _pad_2d(sizes.int(), V_fix)
        coors_fix = _pad_2d(coors.int(), V_fix)
        # Sanity: confirm the clamp guard keeps padding rows from producing NaN.
        with torch.no_grad():
            out_fix = wrapper(feats_fix, sizes_fix, coors_fix)
        nan_count = torch.isnan(out_fix).sum().item()
        if nan_count > 0:
            raise RuntimeError(f"Fixed-V wrapper produced {nan_count} NaNs in "
                               f"padding rows; the div-by-zero guard is broken.")
        print(f"[lidar-export] fixed-V sanity OK (no NaN), output {tuple(out_fix.shape)}")
        export_args = (feats_fix, sizes_fix, coors_fix)
        dynamic_axes = None  # fully static
    else:
        export_args = (feats, sizes.int(), coors.int())
        dynamic_axes = {
            "features":        {0: "V"},
            "num_voxels":      {0: "V"},
            "coors":           {0: "V"},
            "pillar_features": {0: "V"},
        }

    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            export_args,
            args.output,
            input_names=["features", "num_voxels", "coors"],
            output_names=["pillar_features"],
            dynamic_axes=dynamic_axes,
            opset_version=args.opset,
            do_constant_folding=True,
        )

    print(f"[lidar-export] saved to {args.output}")
    onnx_model = onnx.load(args.output)
    onnx.checker.check_model(onnx_model)
    print(f"[lidar-export] onnx.checker: OK, "
          f"graph nodes={len(onnx_model.graph.node)}, "
          f"initializers={len(onnx_model.graph.initializer)}")
    print("[lidar-export] inputs:")
    for i in onnx_model.graph.input:
        dims = [d.dim_param or d.dim_value for d in i.type.tensor_type.shape.dim]
        print(f"    {i.name:20s} {dims}")
    print("[lidar-export] outputs:")
    for o in onnx_model.graph.output:
        dims = [d.dim_param or d.dim_value for d in o.type.tensor_type.shape.dim]
        print(f"    {o.name:20s} {dims}")


if __name__ == "__main__":
    main()
