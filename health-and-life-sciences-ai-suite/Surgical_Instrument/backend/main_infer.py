"""Standalone inference CLI — reads a video, writes an annotated MP4 + CSV.

Usage:
    python -m backend.main_infer \
        --ir models/yolo11n_polyp/best_openvino_model \
        --video videos/polyp_test.mp4 \
        --device gpu \
        --out-video out/annotated.mp4 \
        --out-csv out/per_frame.csv \
        --target-fps 30

Mirrors the POC ``st2_app bench`` behavior so we can regression-test the
port before wiring it into the Flask backend.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.bootstrap.config import load_config
from backend.pipeline.inference import run_batch_annotated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(Path(__file__).parent / "config" / "model.yaml"))
    ap.add_argument("--ir", help="Override: OpenVINO IR directory")
    ap.add_argument("--video", help="Override: input video path")
    ap.add_argument("--device", choices=("cpu", "gpu", "npu"), help="Override: inference device")
    ap.add_argument("--out-video", default="out/annotated.mp4")
    ap.add_argument("--out-csv", default="out/per_frame.csv")
    ap.add_argument("--target-fps", type=float, help="Override: paced FPS target")
    ap.add_argument("--no-annotate", action="store_true", help="Skip drawing + video writing")
    args = ap.parse_args()

    cfg = load_config(args.config)
    ir_dir = Path(args.ir or cfg["model"]["ir_dir"])
    video = Path(args.video or cfg["pipeline"]["default_video"])
    device = args.device or cfg["pipeline"]["device"]
    target_fps = float(args.target_fps or cfg["pipeline"]["target_fps"])
    output_size = tuple(cfg["pipeline"]["output_size"])
    infer_size = int(cfg["pipeline"]["infer_size"])
    warmup = int(cfg["pipeline"]["warmup_frames"])

    if not ir_dir.exists():
        print(f"[main_infer] IR not found: {ir_dir} — run `python -m backend.main_bootstrap` first",
              file=sys.stderr)
        return 2
    if not video.exists():
        print(f"[main_infer] video not found: {video}", file=sys.stderr)
        return 2

    stats = run_batch_annotated(
        ir_dir=ir_dir,
        video_in=video,
        device=device,
        out_video=Path(args.out_video),
        out_csv=Path(args.out_csv),
        output_size=output_size,
        infer_size=infer_size,
        target_fps=target_fps,
        warmup_frames=warmup,
        annotate=not args.no_annotate,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
