"""
Download Utility - Manually download model and video files.

Usage:
    python scripts/download_assets.py
    
    python scripts/download_assets.py --model-only
    python scripts/download_assets.py --video-only
"""

import urllib.request
from pathlib import Path
from tqdm import tqdm
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def download_file(url: str, dest: Path, desc: str = "Downloading") -> None:
    """Download file with progress bar."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    class DownloadProgressBar(tqdm):
        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.update(b * bsize - self.n)

    with DownloadProgressBar(
        unit='B',
        unit_scale=True,
        miniters=1,
        desc=desc
    ) as t:
        urllib.request.urlretrieve(url, dest, reporthook=t.update_to)


def download_model() -> None:
    """Download MTTS-CAN model weights."""
    MODEL_URL = "https://github.com/xliucs/MTTS-CAN/raw/main/mtts_can.hdf5"
    model_path = Path("/models") / "rppg" / "mtts_can.hdf5"

    if model_path.exists():
        logger.info(f"Model already exists: {model_path}")
        size_mb = model_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Size: {size_mb:.1f} MB")
        return

    logger.info("Downloading MTTS-CAN model...")
    logger.info(f"  Source: {MODEL_URL}")
    logger.info(f"  Destination: {model_path}")

    try:
        download_file(MODEL_URL, model_path, "Model")
        logger.info("✓ Model downloaded successfully")
        size_mb = model_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Size: {size_mb:.1f} MB")
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        raise


def download_video() -> None:
    """Download sample video."""
    VIDEO_URL = "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi"
    video_path = Path("/videos") / "rppg" / "sample.mp4"

    if video_path.exists():
        logger.info(f"Video already exists: {video_path}")
        size_mb = video_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Size: {size_mb:.1f} MB")
        return

    logger.info("Downloading sample video...")
    logger.info(f"  Source: {VIDEO_URL}")
    logger.info(f"  Destination: {video_path}")

    try:
        download_file(VIDEO_URL, video_path, "Video")
        logger.info("✓ Video downloaded successfully")
        size_mb = video_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Size: {size_mb:.1f} MB")
    except Exception as e:
        logger.error(f"Failed to download video: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Download RPPG service assets")
    parser.add_argument("--model-only", action="store_true", help="Download only the model")
    parser.add_argument("--video-only", action="store_true", help="Download only the video")

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("RPPG Service Asset Downloader")
    logger.info("=" * 70)
    logger.info("")

    try:
        if args.model_only:
            download_model()
        elif args.video_only:
            download_video()
        else:
            download_model()
            logger.info("")
            download_video()

        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ All assets ready!")
        logger.info("=" * 70)
        logger.info("")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
