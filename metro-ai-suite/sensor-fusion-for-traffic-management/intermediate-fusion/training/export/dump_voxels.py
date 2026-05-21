#!/usr/bin/env python3
"""Dump voxel_features / voxel_indices per frame for NNCF calibration.

The unified ONNX expects two lidar-side inputs that the quantization calibrator
cannot produce on its own:
  voxel_features  [N, 4]  f32   mean of raw point feats per voxel
  voxel_indices   [N, 4]  i32   (batch=0, z, y, x)

Run in bevEnv (py3.8, torch 1.11, mmdet3d compiled ops):
  /home/jie/env/bevEnv/bin/python export/dump_voxels.py \
      configs/V2X-I/det/centerhead/secfpn/camera+lidar/resnet34/bevpoolv2.yaml \
      work_dirs/bevpoolv2/epoch_100.pth \
      -o export/calib_voxels/ --num-frames 400
"""

import argparse
from functools import partial
import os
import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import torch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mmdet3d.utils import recursive_eval


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("config")
    p.add_argument("checkpoint")
    p.add_argument("--output-dir", "-o", default="/home/jie/workspace/bevfusion/export/calib_voxels")
    p.add_argument("--num-frames", type=int, default=400)
    p.add_argument("--split", default="val", choices=["train", "val", "test"],
                   help="dataset split used as data source")
    return p.parse_args()


def _iter_from_dataset(cfg, split, num_frames):
    from mmdet3d.datasets import build_dataloader, build_dataset
    from mmdet3d.datasets.v2x_dataset import collate_fn

    dataset = build_dataset(cfg.data[split])
    dataflow = build_dataloader(
        dataset,
        samples_per_gpu=1,
        workers_per_gpu=cfg.data.workers_per_gpu,
        dist=False,
        shuffle=False,
    )
    dataflow.collate_fn = partial(collate_fn, is_return_depth=False)

    n = 0
    for idx, batch in enumerate(dataflow):
        if n >= num_frames:
            break
        yield f"{idx:05d}", batch
        n += 1


def main():
    args = parse_args()

    from torchpack.utils.config import configs
    from mmcv import Config
    from mmcv.runner import load_checkpoint
    from mmdet3d.models import build_model

    configs.load(args.config, recursive=True)
    cfg = Config(recursive_eval(configs), filename=args.config)
    cfg.model.train_cfg = None
    test_cfg = cfg["model"]["heads"]["object"]["test_cfg"]
    model = build_model(cfg.model, test_cfg=test_cfg)
    load_checkpoint(model, args.checkpoint, map_location="cpu")
    model.cuda().eval()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"using cfg.data.{args.split} as source, writing to {args.output_dir}")
    source_iter = _iter_from_dataset(cfg, args.split, args.num_frames)

    manifest = []
    for i, (fid, data) in enumerate(source_iter):
        points = data["points"]
        if not isinstance(points, list):
            points = [points]
        points = [x.data if hasattr(x, "data") else x for x in points]
        points = [x.cuda() for x in points]

        with torch.no_grad():
            feats, coords, _ = model.voxelize(points)

        feats_np = feats.cpu().numpy().astype(np.float32)
        # coords is [N, 4] = (batch, z, y, x); batch is 0 for single frame, cast to i32.
        coords_np = coords.cpu().numpy().astype(np.int32)

        # img comes through as (1, 1, 3, 864, 1536); drop outer batch dims to (1, 3, 864, 1536).
        img_tensor = data["img"]
        img_t = img_tensor.data if hasattr(img_tensor, "data") else img_tensor
        img_np = img_t.cpu().numpy()[0, 0][None].astype(np.float32)  # [1, 3, H, W]

        np.save(os.path.join(args.output_dir, f"{fid}_voxel_features.npy"), feats_np)
        np.save(os.path.join(args.output_dir, f"{fid}_voxel_indices.npy"), coords_np)
        np.save(os.path.join(args.output_dir, f"{fid}_img.npy"), img_np)
        manifest.append(fid)

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{args.num_frames}] {fid}  voxels={feats_np.shape[0]}  img={img_np.shape}")

    if not manifest:
        raise SystemExit(
            "No frames were dumped. Check dataset split and config paths."
        )

    if len(manifest) < args.num_frames:
        print(
            f"warning: requested {args.num_frames} but only dumped {len(manifest)} frame(s)."
        )

    print(f"  [{len(manifest)}/{args.num_frames}] {manifest[-1]}  done")

    with open(os.path.join(args.output_dir, "manifest.txt"), "w") as f:
        f.write("\n".join(manifest) + "\n")
    print(f"done: {len(manifest)} frames dumped, manifest written")


if __name__ == "__main__":
    main()
