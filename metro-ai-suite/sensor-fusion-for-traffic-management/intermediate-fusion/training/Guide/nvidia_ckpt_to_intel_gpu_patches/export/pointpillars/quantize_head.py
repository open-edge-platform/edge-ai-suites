#!/usr/bin/env python3
"""
NNCF PTQ for the PP head ONNX (decoder backbone + neck + CenterHead).

Input:
    fused_bev [1, 80, 128, 128]
Outputs:
    task{0,1}_{score, reg, height, dim, rot, vel}  (12 tensors)

Calibration source: PT model's real `fused_bev` output.

Usage:
    python export/pointpillars/quantize_head.py \\
        [--onnx export/onnx/pointpillars/head.onnx] \\
        [--out  export/onnx/pointpillars/quantized_head.xml] \\
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
    p = argparse.ArgumentParser(description="INT8 quantize PP head ONNX")
    p.add_argument("--config", default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("--onnx", default="export/onnx/pointpillars/head.onnx")
    p.add_argument("--out",  default="export/onnx/pointpillars/quantized_head.xml")
    p.add_argument("--num-samples", type=int, default=300)
    p.add_argument("--split", default="val", choices=["val", "train"])
    return p.parse_args()


class HeadCalibList:
    def __init__(self, model, cfg, num_samples, split):
        self.samples = []
        for data in calib_samples(cfg, num_samples, split=split):
            feats = pt_extract_all(model, data, fixed_V=None)
            # §37: head now takes decoder_out (post fuser+decoder.backbone+decoder.neck)
            self.samples.append(feats["decoder_out"])
        print(f"[head-quant] collected {len(self.samples)} calib samples")

    def __getitem__(self, idx):
        return self.samples[idx]

    def __len__(self):
        return len(self.samples)


def main():
    args = parse_args()
    model, cfg = build_pt_model(args.config, args.ckpt)
    print(f"[head-quant] PT model loaded from {args.ckpt}")

    calib = HeadCalibList(model, cfg, args.num_samples, args.split)
    del model
    import torch; torch.cuda.empty_cache()

    dataloader = DataLoader(calib, batch_size=1, shuffle=False,
                            collate_fn=lambda x: x[0])

    def transform_fn(x):
        # Head's ONNX input is named "middle" to match the legacy
        # v2xfusion head.bbox.xml (see export-head.py).
        return {"middle": np.ascontiguousarray(x)}

    ov_model = ov.Core().read_model(args.onnx)

    print("[head-quant] starting NNCF quantization...")
    q_model = nncf.quantize(
        ov_model, nncf.Dataset(dataloader, transform_fn),
        fast_bias_correction=False,
        target_device=nncf.TargetDevice.GPU,
        subset_size=len(calib),
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    ov.save_model(q_model, args.out)
    print(f"[head-quant] saved {args.out}")


if __name__ == "__main__":
    main()
