#!/usr/bin/env python3
"""
Export PointPillars-based BEVFusion's CenterHead-only to ONNX.

§37 moved decoder.backbone + decoder.neck into the fuser ONNX (see
export-fuser.py). As a result this head ONNX now only contains:

    middle [1, 256, 128, 128]  (= decoder_out)
    └─ CenterHead.shared_conv  (256 → 64)
    └─ for each task:
          score, reg, height, dim, rot, vel  (each [1, C, H, W])

The input is named `middle` to match the legacy v2xfusion head.bbox.xml
so the deploy-side name-matcher in bev_head.cpp still binds it by name
and we don't need any C++ changes.

For the V2X-I PP centerhead config there are 2 tasks (output names aligned
with bev_head.cpp:228-240):
    task0 = ["car","truck","construction_vehicle","bus","trailer"]       -> score/reg/height/dim/rot/vel
    task1 = ["barrier","motorcycle","bicycle","pedestrian","traffic_cone"] -> score2/reg2/height2/dim2/rot2/vel2

Usage:
    python export/pointpillars/export-head.py \\
        --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \\
        --ckpt   work_dirs/V2X-I/pp/latest.pth \\
        -o       export/onnx/pointpillars/head.onnx
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


class HeadExportWrapper(nn.Module):
    """CenterHead.forward_single (shared_conv + task heads, no NMS)."""

    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.head = model.heads["object"]

    def forward(self, middle: torch.Tensor):
        x = self.head.shared_conv(middle)
        outputs = []
        for task in self.head.task_heads:
            r = task(x)
            # Order must match the output_names list in torch.onnx.export below
            outputs.append(r["heatmap"])
            outputs.append(r["reg"])
            outputs.append(r["height"])
            outputs.append(r["dim"])
            outputs.append(r["rot"])
            if "vel" in r:
                outputs.append(r["vel"])
        return tuple(outputs)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export PP decoder+head ONNX")
    p.add_argument("--config",
                   default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("-o", "--output",
                   default="export/onnx/pointpillars/head.onnx")
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

    # Input to this head is the decoder output, which is produced by
    # export-fuser.py's FuserExportWrapper. For the PP resnet34 config that
    # tensor is [1, 256, 128, 128] — derived from decoder.neck.out_channels
    # in the config (see the `neck:` block under `decoder:`).
    neck_out_ch = int(cfg.model.decoder.neck.out_channels)  # 256
    scatter = model.encoders["lidar"]["backbone"].pts_middle_encoder
    bev_h, bev_w = int(scatter.nx), int(scatter.ny)

    wrapper = HeadExportWrapper(model).cuda().eval()
    middle = torch.randn(1, neck_out_ch, bev_h, bev_w).cuda()

    # Build output names matching wrapper.forward order AND matching the
    # deploy side expectation (bev_head.cpp:228-240 assignOutputPortByName):
    #   task 0: score / rot / dim / reg / height / vel
    #   task 1: score2 / rot2 / dim2 / reg2 / height2 / vel2
    # The wrapper emits heatmap in slot 0 — aliased to "score" here, because
    # that's what the CenterHead post-process expects as "classification score".
    output_names = []
    num_tasks = len(model.heads["object"].task_heads)
    for t in range(num_tasks):
        suffix = "" if t == 0 else str(t + 1)
        # Order must match the tuple order in HeadExportWrapper.forward.
        output_names.extend([
            f"score{suffix}",
            f"reg{suffix}",
            f"height{suffix}",
            f"dim{suffix}",
            f"rot{suffix}",
        ])
        if "vel" in model.heads["object"].task_heads[t].heads:
            output_names.append(f"vel{suffix}")

    with torch.no_grad():
        ref_outs = wrapper(middle)
    assert len(ref_outs) == len(output_names), \
        f"output count mismatch: {len(ref_outs)} tensors vs {len(output_names)} names"
    print(f"[head-export] {num_tasks} tasks, {len(output_names)} output tensors")
    for name, tensor in zip(output_names, ref_outs):
        print(f"    {name:20s} {tuple(tensor.shape)}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (middle,),
            args.output,
            # Input named "middle" — matches the legacy v2xfusion head.bbox.xml
            # so deploy's bev_head.cpp binds it by name without changes.
            input_names=["middle"],
            output_names=output_names,
            opset_version=args.opset,
            do_constant_folding=True,
        )
    print(f"[head-export] saved to {args.output}")
    onnx_model = onnx.load(args.output)
    onnx.checker.check_model(onnx_model)
    print(f"[head-export] onnx.checker: OK, "
          f"graph nodes={len(onnx_model.graph.node)}")


if __name__ == "__main__":
    main()
