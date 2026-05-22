#!/usr/bin/env python3
"""
NNCF PTQ for the PP camera backbone ONNX.

Input name:   img  [1, 3, 864, 1536]   float32
Outputs:      camera_feature          [1, 80, 54, 96]   float32
              camera_depth_weights    [1, 90, 54, 96]   float32

Usage:
    python export/pointpillars/quantize_camera_backbone.py \\
        [--config configs/...default.yaml] \\
        [--ckpt work_dirs/V2X-I/pp/latest.pth] \\
        [--onnx export/onnx/pointpillars/camera.backbone.onnx] \\
        [--out  export/onnx/pointpillars/quantized_camera.xml] \\
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
    p = argparse.ArgumentParser(description="INT8 quantize PP camera ONNX")
    p.add_argument("--config", default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("--onnx", default="export/onnx/pointpillars/camera.backbone.onnx")
    p.add_argument("--out",  default="export/onnx/pointpillars/quantized_camera.xml")
    p.add_argument("--num-samples", type=int, default=300)
    p.add_argument("--split", default="val", choices=["val", "train"])
    return p.parse_args()


class CamCalibList:
    def __init__(self, model, cfg, num_samples, split):
        self.samples = []
        for data in calib_samples(cfg, num_samples, split=split):
            feats = pt_extract_all(model, data, fixed_V=None)
            self.samples.append(feats["img_nchw"])
        print(f"[cam-quant] collected {len(self.samples)} calib samples")

    def __getitem__(self, idx):
        return self.samples[idx]

    def __len__(self):
        return len(self.samples)


def main():
    args = parse_args()
    model, cfg = build_pt_model(args.config, args.ckpt)
    print(f"[cam-quant] PT model loaded from {args.ckpt}")

    calib = CamCalibList(model, cfg, args.num_samples, args.split)
    # Free the PT model — nncf.quantize uses only the OV model + the cached
    # numpy calib tensors from here on.
    del model
    import torch; torch.cuda.empty_cache()

    dataloader = DataLoader(calib, batch_size=1, shuffle=False,
                            collate_fn=lambda x: x[0])

    def transform_fn(x):
        return {"img": np.ascontiguousarray(x)}

    ov_model = ov.Core().read_model(args.onnx)
    print(f"[cam-quant] loaded ONNX from {args.onnx}")

    print("[cam-quant] starting NNCF quantization...")
    q_model = nncf.quantize(
        ov_model, nncf.Dataset(dataloader, transform_fn),
        fast_bias_correction=False,
        target_device=nncf.TargetDevice.GPU,
        subset_size=len(calib),
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    ov.save_model(q_model, args.out)
    print(f"[cam-quant] saved {args.out}")


if __name__ == "__main__":
    main()
