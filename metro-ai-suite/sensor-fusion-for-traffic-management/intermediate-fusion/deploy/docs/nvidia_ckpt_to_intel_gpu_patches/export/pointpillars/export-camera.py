#!/usr/bin/env python3
"""
Export PointPillars-based BEVFusion's **camera backbone** to ONNX.

Mirrors v2xfusionDev/export/export-camera.py — everything up to (and including)
depthnet is exported. The bev_pool itself remains a SYCL kernel on the deploy
side (not part of ONNX).

Graph:
    img [1, N, 3, H, W]
    └─ view → backbone (ResNet34)
    └─ neck  (GeneralizedLSSFPN)
    └─ depthnet (Conv2d: 256 → D+C)
        ├─ softmax  → camera_depth_weights [1, N, D, fH, fW]
        └─ split    → camera_feature       [1, N, C, fH, fW]

For the PP resnet34 config (configs/V2X-I/.../camera+pointpillar/resnet34/default.yaml):
    image_size       = [864, 1536]
    feature_size     = [54, 96]   (downsample_factor=16)
    C (out_channels) = 80
    D (depth bins)   = 90         (dbound=[-2.0, 0.0, 90])
    downsample       = 1          (vtransform.downsample is nn.Identity)

Usage:
    python export/pointpillars/export-camera.py \\
        --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \\
        --ckpt   work_dirs/V2X-I/pp/latest.pth \\
        -o       export/onnx/pointpillars/camera.backbone.onnx
"""

import argparse
import os
import sys
import warnings

import torch
import torch.nn as nn
import onnx
from onnxsim import simplify

warnings.filterwarnings("ignore")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class CameraBackboneExportWrapper(nn.Module):
    """Exports resnet backbone + neck + depthnet.

    Outputs (feat, depth) — bev_pool happens outside (SYCL).
    """

    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, img: torch.Tensor):
        # 4D NCHW input [1, 3, H, W] — matches the reference v2xfusion
        # camera.backbone.onnx I/O schema (deploy/src/cam_bev/bev_cam.cpp
        # expects exactly this layout).
        x = self.model.encoders.camera.backbone(img)
        x = self.model.encoders.camera.neck(x)
        if not isinstance(x, torch.Tensor):
            x = x[1] if len(x) > 1 else x[0]

        vt = self.model.encoders.camera.vtransform
        x = vt.depthnet(x)  # [1, D+C, fH, fW]

        D = vt.D
        Cout = vt.C
        depth = x[:, :D].softmax(dim=1)  # [1, D, fH, fW]  NCHW (matches legacy)
        feat = x[:, D:(D + Cout)]        # [1, C, fH, fW]  NCHW
        # Deploy-side bev_pool (bev_sycl.cc::bpkV2) indexes camera_feature
        # with channel-minor stride (NHWC index), paired with X-major rank in
        # camera-geometry.cpp. Training-side scatter/bev_pool also produce
        # X-major BEV, so the fuser/head are trained under that convention.
        # An explicit NHWC permute at the tail physically shuffles ~400k FP16
        # per frame and, worse, forces OV GPU plugin to choose layout-compat
        # conv kernels that run 60% slower than the legacy NCHW-native path
        # (6.5 ms → 10.9 ms on B580, independent measurement).
        #
        # Trick: emit NHWC data but declare it as NCHW via a Reshape. The
        # underlying buffer is already channel-minor (NHWC) after permute, so
        # reshape back to [1, C, H, W] is a metadata-only op. OV GPU plugin
        # sees an NCHW output and picks the fast kernel set; deploy-side
        # bev_pool already expects channel-minor so its indexing is still
        # correct against the physical memory. Net: ~1-2 ms saved, no change
        # to deploy C++ or to the trained weights.
        B, C, fH, fW = feat.shape
        feat = feat.permute(0, 2, 3, 1).contiguous()  # [B, fH, fW, C] NHWC (physical)
        feat = feat.reshape(B, C, fH, fW)             # reinterpret as NCHW shape
        return feat, depth


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export PP camera backbone ONNX")
    p.add_argument("--config",
                   default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("-o", "--output",
                   default="export/onnx/pointpillars/camera.backbone.onnx")
    p.add_argument("--opset", type=int, default=13)
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
    print(f"[cam-export] model loaded from {args.ckpt}")

    vt = model.encoders["camera"]["vtransform"]
    if not isinstance(vt.downsample, nn.Identity):
        print(f"[cam-export] NOTE: downsample != Identity "
              f"({type(vt.downsample).__name__}) — the final conv block is NOT"
              " part of this ONNX. Export it separately if needed.")

    # Input sizing from the config. 4D NCHW (single camera).
    iH, iW = map(int, vt.image_size)
    img = torch.randn(1, 3, iH, iW).cuda()

    wrapper = CameraBackboneExportWrapper(model).cuda().eval()

    # Reference forward, to sanity-check output shapes
    with torch.no_grad():
        ref_feat, ref_depth = wrapper(img)
    print(f"[cam-export] reference shapes: "
          f"feat={tuple(ref_feat.shape)} depth={tuple(ref_depth.shape)}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (img,),
            args.output,
            input_names=["img"],
            output_names=["camera_feature", "camera_depth_weights"],
            opset_version=args.opset,
            do_constant_folding=True,
        )

    print(f"[cam-export] saved to {args.output}")

    # Simplify the exported graph (constant folding + dead-op removal).
    # Without this, tracer-emitted Reshape/Transpose leftovers can cause
    # OpenVINO PPP on the deploy side to pin the wrong layout to the wrong
    # output tensor, silently swapping camera_feature/camera_depth_weights.
    # Matches legacy export-camera.py behaviour.
    onnx_simp, check = simplify(onnx.load(args.output))
    assert check, "Simplified ONNX model could not be validated"
    onnx.save(onnx_simp, args.output)
    print(f"[cam-export] simplified and saved to {args.output}")

    onnx_model = onnx.load(args.output)
    onnx.checker.check_model(onnx_model)
    print(f"[cam-export] onnx.checker: OK, "
          f"graph nodes={len(onnx_model.graph.node)}, "
          f"initializers={len(onnx_model.graph.initializer)}")
    print("[cam-export] inputs:")
    for i in onnx_model.graph.input:
        dims = [d.dim_param or d.dim_value for d in i.type.tensor_type.shape.dim]
        print(f"    {i.name:25s} {dims}")
    print("[cam-export] outputs:")
    for o in onnx_model.graph.output:
        dims = [d.dim_param or d.dim_value for d in o.type.tensor_type.shape.dim]
        print(f"    {o.name:25s} {dims}")


if __name__ == "__main__":
    main()
