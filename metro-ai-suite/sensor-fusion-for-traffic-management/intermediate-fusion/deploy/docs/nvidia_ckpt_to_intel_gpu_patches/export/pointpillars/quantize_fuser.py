#!/usr/bin/env python3
"""
NNCF PTQ for the PP fuser ONNX.

Input names:
    cam_bev   [1, 80, 128, 128]
    lidar_bev [1, 64, 128, 128]
Output:
    fused_bev [1, 80, 128, 128]

Calibration source: PT model's real `cam_bev` and `lidar_bev` (post-scatter)
for every calib frame. Avoids v2xfusionDev's brittle chain of OV-compiled
camera+lidar models.

Usage:
    python export/pointpillars/quantize_fuser.py \\
        [--onnx export/onnx/pointpillars/fuser.onnx] \\
        [--out  export/onnx/pointpillars/quantized_fuser.xml] \\
        [--num-samples 300]
"""

import argparse
import os
import sys

import numpy as np
import nncf
import openvino as ov
from torch.utils.data import DataLoader

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from _calib_data import build_pt_model, calib_samples, pt_extract_all  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description="INT8 quantize PP fuser ONNX")
    p.add_argument("--config", default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("--onnx", default="export/onnx/pointpillars/fuser.onnx")
    p.add_argument("--out",  default="export/onnx/pointpillars/quantized_fuser.xml")
    p.add_argument("--num-samples", type=int, default=300)
    p.add_argument("--split", default="val", choices=["val", "train"])
    return p.parse_args()


class FuserCalibList:
    def __init__(self, model, cfg, num_samples, split):
        self.samples = []
        for data in calib_samples(cfg, num_samples, split=split):
            feats = pt_extract_all(model, data, fixed_V=None)
            self.samples.append({
                "cam_bev":   feats["cam_bev"],
                "lidar_bev": feats["lidar_bev"],
            })
        print(f"[fuser-quant] collected {len(self.samples)} calib samples")

    def __getitem__(self, idx):
        return self.samples[idx]

    def __len__(self):
        return len(self.samples)


def main():
    args = parse_args()
    model, cfg = build_pt_model(args.config, args.ckpt)
    print(f"[fuser-quant] PT model loaded from {args.ckpt}")

    calib = FuserCalibList(model, cfg, args.num_samples, args.split)
    del model
    import torch; torch.cuda.empty_cache()

    dataloader = DataLoader(calib, batch_size=1, shuffle=False,
                            collate_fn=lambda x: x[0])

    def transform_fn(item):
        return {
            "cam_bev":   np.ascontiguousarray(item["cam_bev"]),
            "lidar_bev": np.ascontiguousarray(item["lidar_bev"]),
        }

    ov_model = ov.Core().read_model(args.onnx)

    print("[fuser-quant] starting NNCF quantization...")
    q_model = nncf.quantize(
        ov_model, nncf.Dataset(dataloader, transform_fn),
        fast_bias_correction=False,
        target_device=nncf.TargetDevice.GPU,
        subset_size=len(calib),
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    ov.save_model(q_model, args.out)
    print(f"[fuser-quant] saved {args.out}")


if __name__ == "__main__":
    main()
