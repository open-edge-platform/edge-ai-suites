#!/usr/bin/env python3
"""
Export PointPillars-based BEVFusion's fuser + decoder to ONNX.

Why fuser + decoder fused into one ONNX (§37):
    On Battlemage GPUs (B580/B60) the OpenVINO GPU plugin deadlocks during
    first infer when compiling a large INT8-quantized model to the shared
    ClContext. Our initial split put all of `decoder.backbone + decoder.neck
    + CenterHead` into head.onnx (949 ops after quantization) which triggered
    the deadlock. To match the legacy-v2xfusion split that is known to work,
    we put `ConvFuser + decoder.backbone + decoder.neck` into fuser.onnx
    (outputs [1, 256, 128, 128], naming compatible with legacy head.bbox.xml
    input `middle`), and head.onnx becomes a small CenterHead-only graph.

Graph:
    cat(cam_bev, lidar_bev) → ConvFuser → decoder.backbone → decoder.neck
    → decoder_out [1, 256, 128, 128]

I/O shapes for the PP resnet34 config:
    cam_bev     [1, 80,  128, 128]
    lidar_bev   [1, 64,  128, 128]  (after PointPillarsScatter on deploy side)
    decoder_out [1, 256, 128, 128]  (named `middle` for legacy-compat so deploy
                                     bev_head.cpp's name-based matcher binds it
                                     as the head input)

Usage:
    python export/pointpillars/export-fuser.py \\
        --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \\
        --ckpt   work_dirs/V2X-I/pp/latest.pth \\
        -o       export/onnx/pointpillars/fuser.onnx
"""

import argparse
import os
import sys
import warnings

import torch
import torch.nn as nn
import onnx

warnings.filterwarnings("ignore")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class FuserExportWrapper(nn.Module):
    """ConvFuser + decoder.backbone + decoder.neck.

    Output is the tensor CenterHead.shared_conv expects as input.
    """

    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.fuser = model.fuser
        self.decoder_backbone = model.decoder["backbone"]
        self.decoder_neck = model.decoder["neck"]

    def forward(self, cam_bev: torch.Tensor, lidar_bev: torch.Tensor) -> torch.Tensor:
        x = self.fuser([cam_bev, lidar_bev])
        x = self.decoder_backbone(x)
        x = self.decoder_neck(x)
        if isinstance(x, (list, tuple)):
            x = x[0]
        return x


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export PP fuser ONNX")
    p.add_argument("--config",
                   default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("-o", "--output",
                   default="export/onnx/pointpillars/fuser.onnx")
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

    in_channels = list(cfg.model.fuser.in_channels)  # [80, 64]
    cam_ch, lidar_ch = int(in_channels[0]), int(in_channels[1])
    # BEV size comes from PointPillarsScatter output_shape [128, 128]
    scatter = model.encoders["lidar"]["backbone"].pts_middle_encoder
    bev_h, bev_w = int(scatter.nx), int(scatter.ny)
    print(f"[fuser-export] cam_bev=[1,{cam_ch},{bev_h},{bev_w}] "
          f"lidar_bev=[1,{lidar_ch},{bev_h},{bev_w}]")

    wrapper = FuserExportWrapper(model).cuda().eval()
    cam_bev = torch.randn(1, cam_ch, bev_h, bev_w).cuda()
    lidar_bev = torch.randn(1, lidar_ch, bev_h, bev_w).cuda()

    with torch.no_grad():
        ref_out = wrapper(cam_bev, lidar_bev)
    print(f"[fuser-export] ref output shape: {tuple(ref_out.shape)}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (cam_bev, lidar_bev),
            args.output,
            # Output named "middle" — this matches the legacy v2xfusion
            # head.bbox.xml input name so bev_head.cpp's name-based matcher
            # binds it cleanly; bev_fuser.cpp auto-recognises any first
            # output as fused.
            input_names=["cam_bev", "lidar_bev"],
            output_names=["middle"],
            opset_version=args.opset,
            do_constant_folding=True,
        )

    print(f"[fuser-export] saved to {args.output}")
    onnx_model = onnx.load(args.output)
    onnx.checker.check_model(onnx_model)
    print(f"[fuser-export] onnx.checker: OK, "
          f"graph nodes={len(onnx_model.graph.node)}")
    print("[fuser-export] inputs:")
    for i in onnx_model.graph.input:
        dims = [d.dim_param or d.dim_value for d in i.type.tensor_type.shape.dim]
        print(f"    {i.name:15s} {dims}")
    print("[fuser-export] outputs:")
    for o in onnx_model.graph.output:
        dims = [d.dim_param or d.dim_value for d in o.type.tensor_type.shape.dim]
        print(f"    {o.name:15s} {dims}")


if __name__ == "__main__":
    main()
