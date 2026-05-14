#!/usr/bin/env python3
"""
Convenience entry point: export all 4 PointPillars-based BEVFusion ONNX models.

Runs in sequence:
    1. export-camera.py  → camera.backbone.onnx
    2. export-lidar.py   → lidar_pfe.onnx       (PFE-only)
    3. export-fuser.py   → fuser.onnx
    4. export-head.py    → head.onnx

Usage:
    python export/pointpillars/export_all.py \\
        --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \\
        --ckpt   work_dirs/V2X-I/pp/latest.pth \\
        --out-dir export/onnx/pointpillars
"""

import argparse
import os
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export all 4 PP ONNX models")
    p.add_argument("--config",
                   default="configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml")
    p.add_argument("--ckpt", default="work_dirs/V2X-I/pp/latest.pth")
    p.add_argument("--out-dir", default="export/onnx/pointpillars")
    p.add_argument("--python", default=sys.executable,
                   help="Python interpreter to use")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    here = os.path.dirname(os.path.abspath(__file__))
    jobs = [
        ("camera", "export-camera.py", "camera.backbone.onnx"),
        ("lidar",  "export-lidar.py",  "lidar_pfe.onnx"),
        ("fuser",  "export-fuser.py",  "fuser.onnx"),
        ("head",   "export-head.py",   "head.onnx"),
    ]

    results = []
    for tag, script, fname in jobs:
        out_path = os.path.join(args.out_dir, fname)
        cmd = [
            args.python, os.path.join(here, script),
            "--config", args.config,
            "--ckpt", args.ckpt,
            "-o", out_path,
        ]
        print(f"\n{'=' * 70}\n[{tag}] {' '.join(cmd)}\n{'=' * 70}")
        ret = subprocess.run(cmd, cwd=os.path.dirname(here).rsplit("/export", 1)[0])
        results.append((tag, out_path, ret.returncode == 0))

    print(f"\n{'=' * 70}\nSUMMARY\n{'=' * 70}")
    for tag, out_path, ok in results:
        tag_ok = "OK " if ok else "FAIL"
        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        print(f"  [{tag_ok}] {tag:8s} {out_path}  ({size:,} bytes)")

    if not all(ok for _, _, ok in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
