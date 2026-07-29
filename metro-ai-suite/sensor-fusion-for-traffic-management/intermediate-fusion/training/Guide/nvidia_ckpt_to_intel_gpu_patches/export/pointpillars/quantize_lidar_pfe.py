#!/usr/bin/env python3
"""
NNCF PTQ for the PP lidar PFE ONNX.

Input names (must match export-lidar.py exactly):
    features   [V|V_max, 100, 4]   float32
    num_voxels [V|V_max]           int32
    coors      [V|V_max, 4]        int32
Output:
    pillar_features [V|V_max, 64]  float32

The script reads the target ONNX's `features` input shape to decide:
    - static V (features has a concrete dim[0]): we pad each frame to V_max
      before feeding calibration, and the saved INT8 model retains the
      static shape.
    - dynamic V: we feed each frame at its natural V.

Usage:
    python export/pointpillars/quantize_lidar_pfe.py \\
        [--onnx export/onnx/pointpillars/lidar_pfe_v7000.onnx] \\
        [--out  export/onnx/pointpillars/quantized_lidar_pfe.xml] \\
        [--num-samples 300]
"""

import argparse
import os
import sys

import numpy as np
import nncf
import openvino as ov
import onnx
from torch.utils.data import DataLoader

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from _calib_data import build_pt_model, calib_samples, pt_extract_all  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description="INT8 quantize PP lidar PFE ONNX")
    p.add_argument("--config", default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    # Default to the static-V ONNX (§35): it's the faster one on deploy and
    # easier for nncf to quantize (fully static shapes).
    p.add_argument("--onnx", default="export/onnx/pointpillars/lidar_pfe_v7000.onnx")
    p.add_argument("--out",  default="export/onnx/pointpillars/quantized_lidar_pfe.xml")
    p.add_argument("--num-samples", type=int, default=300)
    p.add_argument("--split", default="val", choices=["val", "train"])
    return p.parse_args()


def detect_fixed_v(onnx_path: str):
    """Return V if features input is statically shaped, else None."""
    m = onnx.load(onnx_path)
    for inp in m.graph.input:
        if inp.name != "features":
            continue
        dims = inp.type.tensor_type.shape.dim
        if all(d.dim_value > 0 for d in dims):
            return int(dims[0].dim_value)
        return None
    raise RuntimeError(f"no input named 'features' in {onnx_path}")


class LidarPfeCalibList:
    def __init__(self, model, cfg, num_samples, split, fixed_V):
        self.samples = []
        max_V_seen = 0
        for data in calib_samples(cfg, num_samples, split=split):
            feats = pt_extract_all(model, data, fixed_V=fixed_V)
            max_V_seen = max(max_V_seen, int(feats["features"].shape[0]))
            self.samples.append({
                "features":   feats["features"],
                "num_voxels": feats["num_voxels"],
                "coors":      feats["coors"],
            })
        print(f"[pfe-quant] collected {len(self.samples)} calib samples  (max_V_seen={max_V_seen}; fixed_V={fixed_V})")

    def __getitem__(self, idx):
        return self.samples[idx]

    def __len__(self):
        return len(self.samples)


def main():
    args = parse_args()
    fixed_V = detect_fixed_v(args.onnx)
    print(f"[pfe-quant] ONNX {args.onnx}  → fixed_V={fixed_V}")

    model, cfg = build_pt_model(args.config, args.ckpt)
    print(f"[pfe-quant] PT model loaded from {args.ckpt}")

    calib = LidarPfeCalibList(model, cfg, args.num_samples, args.split, fixed_V)
    del model
    import torch; torch.cuda.empty_cache()

    dataloader = DataLoader(calib, batch_size=1, shuffle=False,
                            collate_fn=lambda x: x[0])

    def transform_fn(item):
        return {
            "features":   np.ascontiguousarray(item["features"]),
            "num_voxels": np.ascontiguousarray(item["num_voxels"]),
            "coors":      np.ascontiguousarray(item["coors"]),
        }

    ov_model = ov.Core().read_model(args.onnx)

    # PFE quantization is effectively disabled. NNCF's per-tensor symmetric
    # activation quant can't handle the 9-ch decorated feature tensor whose c3
    # is raw intensity 0..255 but c4..c8 are intra-pillar offsets ±0.7. Step
    # size of ~2.0 (set by c3) destroys c4..c8 precision, and the PFN Linear
    # weights on those rows are ±23 / ±15 — so tiny-input-error × huge-weight
    # blows MatMul output up 20× and pillar_features cos collapses to 0.07.
    # Ignoring only the decoration nodes isn't enough: downstream FQs are
    # re-anchored and leak the error. The minimal safe configuration turns out
    # to ignore essentially every op on the feature path, leaving no op for
    # NNCF to quantize (it prints "The model has no operations to apply
    # quantization"). The saved IR is FP32 but still faster than the raw ONNX
    # (OV runtime folds constants and fuses BN; PFE ~1.3 ms vs 1.5 ms on
    # Battlemage). Since PFE only contributes ~10% of total latency, losing
    # INT8 on it is acceptable; the big INT8 wins are on camera + fuser + head.
    # pillar_features cos vs FP32 ONNX: 1.0 on GPU.1, 0.998 on CPU (FP16 down-
    # cast artefact). Verified end-to-end: --int8 gives 16.1 boxes/frame
    # (matches FP32 baseline 16.0) on V2X-I.
    ignored = nncf.IgnoredScope(
        names=[
            "Cast_1", "Max_2",
            "ReduceSum_11", "Div_12", "Sub_18",
            "Slice_9", "Slice_17",
            "Mul_28", "Sub_31", "Add_30", "Cast_24",
            "Mul_71", "Sub_74", "Add_73", "Cast_67",
            "Concat_115", "Mul_125",
            "MatMul_126",
        ],
        validate=False,
    )

    print("[pfe-quant] starting NNCF quantization...")
    q_model = nncf.quantize(
        ov_model, nncf.Dataset(dataloader, transform_fn),
        fast_bias_correction=False,
        target_device=nncf.TargetDevice.GPU,
        subset_size=len(calib),
        ignored_scope=ignored,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    ov.save_model(q_model, args.out)
    print(f"[pfe-quant] saved {args.out}")


if __name__ == "__main__":
    main()
