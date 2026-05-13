#!/usr/bin/env python3
"""
Entry point — quantize all 4 PointPillars ONNX to INT8 in sequence.

Produces in --out-dir:
    quantized_camera.xml   (+ .bin)
    quantized_lidar_pfe.xml
    quantized_fuser.xml
    quantized_head.xml

Usage:
    python export/pointpillars/quantize_all.py \\
        [--config configs/...default.yaml] \\
        [--ckpt work_dirs/V2X-I/pp/latest.pth] \\
        [--onnx-dir export/onnx/pointpillars] \\
        [--out-dir  export/onnx/pointpillars] \\
        [--num-samples 300]
"""

import argparse
import os
import subprocess
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Quantize all 4 PP ONNX to INT8")
    p.add_argument("--config", default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("--onnx-dir", default="export/onnx/pointpillars")
    p.add_argument("--out-dir",  default="export/onnx/pointpillars")
    p.add_argument("--num-samples", type=int, default=300)
    p.add_argument("--python", default=sys.executable)
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))

    # (tag, script_name, input_onnx_filename, output_xml_filename)
    # PFE: use v6000 to match deploy's max_voxels=6000 for --int8 path
    # (deploy/src/pipeline/split_pipeline_config.cpp:110-127). Fall back to
    # the dynamic-V ONNX only if v6000 is missing.
    pfe_onnx = "lidar_pfe_v6000.onnx" if os.path.exists(
        os.path.join(args.onnx_dir, "lidar_pfe_v6000.onnx")) else "lidar_pfe.onnx"
    jobs = [
        ("camera",    "quantize_camera_backbone.py", "camera.backbone.onnx", "quantized_camera.xml"),
        ("lidar_pfe", "quantize_lidar_pfe.py",       pfe_onnx,               "quantized_lidar_pfe.xml"),
        ("fuser",     "quantize_fuser.py",           "fuser.onnx",           "quantized_fuser.xml"),
        ("head",      "quantize_head.py",            "head.onnx",            "quantized_head.xml"),
    ]

    results = []
    for tag, script, onnx_name, out_name in jobs:
        onnx_path = os.path.join(args.onnx_dir, onnx_name)
        out_path = os.path.join(args.out_dir, out_name)
        cmd = [
            args.python, os.path.join(here, script),
            "--config", args.config, "--ckpt", args.ckpt,
            "--onnx", onnx_path, "--out", out_path,
            "--num-samples", str(args.num_samples),
        ]
        print(f"\n{'=' * 70}\n[{tag}] {' '.join(cmd)}\n{'=' * 70}")
        # cwd = bevfusion repo root (two dirs up from here)
        repo_root = os.path.dirname(os.path.dirname(here))
        rc = subprocess.run(cmd, cwd=repo_root).returncode
        results.append((tag, out_path, rc == 0))

    print(f"\n{'=' * 70}\nSUMMARY\n{'=' * 70}")
    for tag, out_path, ok in results:
        status = "OK" if ok else "FAIL"
        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        print(f"  [{status}] {tag:10s} {out_path}  ({size:,} bytes)")

    if not all(ok for _, _, ok in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
