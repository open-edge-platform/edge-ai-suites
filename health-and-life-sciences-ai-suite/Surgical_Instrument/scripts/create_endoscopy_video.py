#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import cv2
except Exception as exc:
    print(
        "ERROR: OpenCV (cv2) is required. Install dependencies with 'make backend-venv' and run this script via '.venv-backend/bin/python'.",
        file=sys.stderr,
    )
    print(f"DETAIL: {exc}", file=sys.stderr)
    sys.exit(2)


VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
H264_CODEC_CANDIDATES = ("avc1", "H264", "X264")


def _numeric_sort_key(path: Path):
    stem = path.stem
    if stem.isdigit():
        return (0, int(stem))
    return (1, stem.lower())


def _list_images(images_dir: Path) -> list[Path]:
    images = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]
    images.sort(key=_numeric_sort_key)
    return images


def _resize_cover(frame, width: int, height: int):
    src_h, src_w = frame.shape[:2]
    if src_h == 0 or src_w == 0:
        raise ValueError("Encountered an empty image frame")

    scale = max(width / src_w, height / src_h)
    new_w = int(round(src_w * scale))
    new_h = int(round(src_h * scale))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    x0 = (new_w - width) // 2
    y0 = (new_h - height) // 2
    return resized[y0 : y0 + height, x0 : x0 + width]


def _open_video_writer(output: Path, fps: int, width: int, height: int, codec: str):
    """Open a writer using H.264-compatible codecs by default.

    The Surgical Instrument file-source pipeline expects H.264 input.
    """
    requested = codec.strip()
    candidates = H264_CODEC_CANDIDATES if requested.lower() == "auto" else (requested,)

    last_error = None
    for code in candidates:
        try:
            fourcc = cv2.VideoWriter_fourcc(*code)
            writer = cv2.VideoWriter(str(output), fourcc, float(fps), (width, height))
            if writer.isOpened():
                return writer, code
            writer.release()
        except Exception as exc:
            last_error = exc

    hint = " / ".join(H264_CODEC_CANDIDATES)
    detail = f" Last error: {last_error}" if last_error is not None else ""
    raise RuntimeError(
        "Failed to open H.264 writer for output video. "
        f"Tried codecs: {', '.join(candidates)}. "
        f"Use --codec <FOURCC> or keep --codec auto (tries {hint})."
        f"{detail}"
    )


def build_video(
    images_dir: Path,
    output: Path,
    seconds: int,
    fps: int,
    width: int,
    height: int,
    codec: str,
) -> None:
    images = _list_images(images_dir)
    if not images:
        raise FileNotFoundError(f"No images found in {images_dir}")

    output.parent.mkdir(parents=True, exist_ok=True)
    total_frames = seconds * fps

    writer, selected_codec = _open_video_writer(output, fps, width, height, codec)

    print(f"[video] source images : {images_dir}")
    print(f"[video] image count   : {len(images)}")
    print(f"[video] output        : {output}")
    print(f"[video] codec         : {selected_codec}")
    print(f"[video] target        : {width}x{height} @ {fps} fps for {seconds}s ({total_frames} frames)")

    try:
        for i in range(total_frames):
            img_path = images[i % len(images)]
            frame = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if frame is None:
                raise RuntimeError(f"Failed to read image: {img_path}")

            out = _resize_cover(frame, width, height)
            writer.write(out)

            if i == 0 or (i + 1) % 300 == 0 or (i + 1) == total_frames:
                print(f"[video] progress      : {i + 1}/{total_frames}")
    finally:
        writer.release()

    print("[video] done")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_images = repo_root / "datasets" / "CVC-ColonDB" / "raw" / "images"
    default_output = repo_root / "videos" / "polyp_test.mp4"

    parser = argparse.ArgumentParser(
        description="Create a 1080p/60s demo MP4 from endoscopy images for the Surgical Instrument app."
    )
    parser.add_argument("--images-dir", type=Path, default=default_images, help="Directory containing input images")
    parser.add_argument("--output", type=Path, default=default_output, help="Output MP4 path")
    parser.add_argument("--seconds", type=int, default=60, help="Video duration in seconds")
    parser.add_argument("--fps", type=int, default=60, help="Frames per second")
    parser.add_argument("--width", type=int, default=1920, help="Output width")
    parser.add_argument("--height", type=int, default=1080, help="Output height")
    parser.add_argument(
        "--codec",
        type=str,
        default="auto",
        help=(
            "FOURCC codec to use. Default 'auto' tries H.264-compatible codecs "
            f"in order: {', '.join(H264_CODEC_CANDIDATES)}"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.seconds <= 0 or args.fps <= 0:
        print("ERROR: seconds and fps must be positive integers", file=sys.stderr)
        return 2
    if args.width <= 0 or args.height <= 0:
        print("ERROR: width and height must be positive integers", file=sys.stderr)
        return 2
    if not args.images_dir.exists():
        print(f"ERROR: images directory not found: {args.images_dir}", file=sys.stderr)
        return 2

    try:
        build_video(
            images_dir=args.images_dir,
            output=args.output,
            seconds=args.seconds,
            fps=args.fps,
            width=args.width,
            height=args.height,
            codec=args.codec,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
