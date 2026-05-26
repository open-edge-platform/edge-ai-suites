#!/usr/bin/env python3
"""
Precompute BEVPool V2 geometry data (indices and intervals) from a trained model.

After training with bevpoolv2, run this script to generate the geometry files
needed for ONNX export and inference.

Outputs:
  indices.bin   - sorted point indices [uint32 count][count * uint32]
  intervals.bin - interval data [uint32 count][count * int3(start, end, ranks_bev)]

Usage:
  # From dataset (recommended) - loads real data directly from the dataset:
  python precompute_geometry.py <config.yaml> <checkpoint.pth> --from-dataset [-o output_dir]

    # From saved tensor data file:
    python precompute_geometry.py <config.yaml> <checkpoint.pth> --data-path <example-data.pth> [-o output_dir]
"""

import os
import sys
import struct
import argparse
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import torch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mmdet3d.utils import recursive_eval


def save_intervals_to_bin(interval_starts, interval_lengths, ranks_bev, filename):
    """Save intervals as sycl::int3 format bin file."""
    assert len(interval_starts) == len(interval_lengths) == len(ranks_bev)

    num_intervals = len(interval_starts)
    interval_starts = interval_starts.astype(np.int32)
    interval_lengths = interval_lengths.astype(np.int32)
    ranks_bev = ranks_bev.astype(np.int32)
    interval_ends = interval_starts + interval_lengths

    with open(filename, 'wb') as f:
        f.write(struct.pack('I', num_intervals))
        for i in range(num_intervals):
            f.write(struct.pack('iii',
                int(interval_starts[i]),
                int(interval_ends[i]),
                int(ranks_bev[i])))

    print(f"  Intervals saved to {filename}: {num_intervals} intervals")
    print(f"    interval_starts range: [{interval_starts.min()}, {interval_starts.max()}]")
    print(f"    interval_ends range: [{interval_ends.min()}, {interval_ends.max()}]")
    print(f"    ranks_bev range: [{ranks_bev.min()}, {ranks_bev.max()}]")


def save_indices_to_bin(indices, filename):
    """Save indices as uint32 bin file."""
    indices_uint32 = indices.astype(np.uint32)

    with open(filename, 'wb') as f:
        f.write(struct.pack('I', len(indices_uint32)))
        f.write(indices_uint32.tobytes())

    print(f"  Indices saved to {filename}: {len(indices_uint32)} indices")

def to_cuda(val):
    """Move a tensor or DataContainer to CUDA."""
    if isinstance(val, torch.Tensor):
        return val.cuda()
    if hasattr(val, 'data'):
        return val.data.cuda()
    return val


def compute_geometry_from_data(model, vtransform, data):
    """Compute geometry indices/intervals from a data dict."""
    img = to_cuda(data["img"])

    camera2lidar = to_cuda(data["camera2lidar"])
    camera_intrinsics = to_cuda(data["camera_intrinsics"])
    img_aug_matrix = to_cuda(data["img_aug_matrix"])
    lidar_aug_matrix = to_cuda(data["lidar_aug_matrix"])

    denorms = None
    if "denorms" in data:
        denorms = to_cuda(data["denorms"])

    with torch.no_grad():
        geom = vtransform.get_geometry_rays(
            camera2lidar, camera_intrinsics,
            img_aug_matrix, lidar_aug_matrix, denorms,
        )

        # Run backbone + neck + depthnet to get depth prediction
        B, N = img.shape[:2]
        x_cam = model.encoders["camera"]["backbone"](img.view(-1, *img.shape[2:]))
        x_cam = model.encoders["camera"]["neck"](x_cam)
        if not isinstance(x_cam, torch.Tensor):
            x_cam = x_cam[1]
        BN, C, fH, fW = x_cam.shape
        x_cam = x_cam.view(B, BN // B, C, fH, fW)

        x_flat = x_cam.view(B * (BN // B), C, fH, fW)
        x_dn = vtransform.depthnet(x_flat)
        depth = x_dn[:, :vtransform.D].softmax(dim=1)
        depth = depth.view(B, BN // B, vtransform.D, fH, fW)
        depth_kept = (depth >= vtransform.depth_threshold)

        ranks_bev, ranks_depth, ranks_feat, \
        interval_starts, interval_lengths, indices = \
            vtransform.voxel_pooling_prepare_v2(geom, depth_kept)

    return ranks_bev, ranks_depth, ranks_feat, interval_starts, interval_lengths, indices


def parse_args():
    parser = argparse.ArgumentParser(description="Precompute BEVPool V2 geometry")
    parser.add_argument("config", help="torchpack config YAML")
    parser.add_argument("checkpoint", help="checkpoint .pth")

    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-dataset", action="store_true",
                        help="Load real data from the dataset (recommended)")
    source.add_argument("--data-path", type=str, default=None,
                        help="Path to example-data.pth saved as tensors only")

    parser.add_argument("--split", type=str, default="val", choices=["train", "val"],
                        help="Dataset split to use with --from-dataset (default: val)")
    parser.add_argument("--sample-idx", type=int, default=0,
                        help="Sample index to use with --from-dataset (default: 0)")
    parser.add_argument("--output-dir", "-o", type=str, default="./export/geometry",
                        help="Output directory for bin files")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  BEVPool V2 Geometry Precomputation")
    print("=" * 60)

    # Load config & model
    print("\n[1/3] Loading model ...")
    from torchpack.utils.config import configs
    from mmcv import Config
    from mmcv.runner import load_checkpoint
    from mmdet3d.models import build_model

    configs.load(args.config, recursive=True)
    cfg = Config(recursive_eval(configs), filename=args.config)
    cfg.model.train_cfg = None

    test_cfg = cfg["model"]["heads"]["object"]["test_cfg"]
    model = build_model(cfg.model, test_cfg=test_cfg)
    load_checkpoint(model, args.checkpoint, map_location='cpu')
    model.cuda().eval()

    vtransform = model.encoders["camera"]["vtransform"]
    print(f"  vtransform type: {type(vtransform).__name__}")
    print(f"  D={vtransform.D}, C={vtransform.C}")
    print(f"  nx={vtransform.nx.tolist()}")
    print(f"  depth_threshold={vtransform.depth_threshold:.6f}")

    # Load data
    print("\n[2/3] Computing geometry ...")

    if args.from_dataset:
        # Load directly from the dataset
        from functools import partial
        from mmdet3d.datasets import build_dataloader, build_dataset
        from mmdet3d.datasets.v2x_dataset import collate_fn

        print(f"  Loading from dataset (split={args.split}, sample_idx={args.sample_idx}) ...")
        dataset = build_dataset(cfg.data[args.split])
        dataflow = build_dataloader(
            dataset,
            samples_per_gpu=1,
            workers_per_gpu=cfg.data.workers_per_gpu,
            dist=False,
            shuffle=False,
        )
        dataflow.collate_fn = partial(collate_fn, is_return_depth=False)

        data = None
        for idx, batch in enumerate(dataflow):
            if idx == args.sample_idx:
                data = batch
                break
        assert data is not None, f"Sample index {args.sample_idx} not found in dataset"
        print(f"  Loaded sample #{args.sample_idx}")

        ranks_bev, ranks_depth, ranks_feat, \
        interval_starts, interval_lengths, indices = \
            compute_geometry_from_data(model, vtransform, data)

    elif args.data_path and os.path.exists(args.data_path):
        print(f"  Loading tensor data from {args.data_path}")
        data = torch.load(args.data_path, weights_only=True)

        ranks_bev, ranks_depth, ranks_feat, \
        interval_starts, interval_lengths, indices = \
            compute_geometry_from_data(model, vtransform, data)

    else:
        print("  No data source specified, using dummy geometry")
        print("  WARNING: For real deployment, use --from-dataset or --data-path")

        B, N = 1, 1
        fH, fW = map(int, vtransform.feature_size)
        D = vtransform.D
        num_points = B * N * D * int(fH) * int(fW)

        indices = torch.arange(num_points, dtype=torch.int32, device='cuda')
        bev_w = int(vtransform.nx[0].item())
        bev_h = int(vtransform.nx[1].item())
        bev_size = bev_h * bev_w

        chunk = 64
        starts = torch.arange(0, num_points, chunk, dtype=torch.int32, device='cuda')
        lengths = torch.clamp(starts + chunk, max=num_points) - starts
        ranks_bev = torch.arange(starts.shape[0], dtype=torch.int32, device='cuda') % bev_size
        interval_starts = starts
        interval_lengths = lengths

    # bev_latest format: keep ALL indices (full B*N*D*fH*fW) and ALL intervals
    # including sentinel (rank=-1). Offsets are ABSOLUTE into the full array.
    # OV runtime handles sentinel: OCL kernel checks out_index < 0 and skips.
    ranks_bev_np = ranks_bev.cpu().numpy()
    interval_starts_np = interval_starts.cpu().numpy()
    interval_lengths_np = interval_lengths.cpu().numpy()
    indices_np = indices.cpu().numpy()

    n_sentinel = int((ranks_bev_np < 0).sum())
    if n_sentinel > 0:
        print(f"  Sentinel: {n_sentinel} interval(s) with rank=-1 (kept, bev_latest format)")
    print(f"  Total points: {len(indices_np)} (full grid, no stripping)")

    # Save
    print("\n[3/3] Saving geometry files ...")
    os.makedirs(args.output_dir, exist_ok=True)

    save_indices_to_bin(indices_np, os.path.join(args.output_dir, "indices.bin"))
    save_intervals_to_bin(interval_starts_np, interval_lengths_np, ranks_bev_np,
                          os.path.join(args.output_dir, "intervals.bin"))

    torch.save({
        'indices': indices.cpu(),
        'interval_starts': interval_starts.cpu(),
        'interval_lengths': interval_lengths.cpu(),
        'ranks_bev': ranks_bev.cpu(),
    }, os.path.join(args.output_dir, "geometry.pth"))
    print(f"  Geometry tensors saved to {os.path.join(args.output_dir, 'geometry.pth')}")

    print(f"\nGeometry precomputation complete!")
    print(f"  Output dir: {args.output_dir}")
    print(f"  Total indices: {len(indices_np)}")
    print(f"  Total intervals: {len(interval_starts_np)}")


if __name__ == "__main__":
    main()
