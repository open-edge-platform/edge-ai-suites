"""Download and convert RPPG assets.

This script:

1. Downloads the MTTS-CAN Keras HDF5 model into /models/rppg/mtts_can.hdf5
2. Converts it to OpenVINO IR (XML+BIN) for Intel iGPU inference
3. Downloads the sample video into /videos/rppg/sample.mp4

Usage:
    python scripts/rppg_download_assets.py

    python scripts/rppg_download_assets.py --model-only
    python scripts/rppg_download_assets.py --video-only
"""

import urllib.request
from pathlib import Path
from tqdm import tqdm
import logging
import argparse

import tensorflow as tf
from tensorflow import keras
import openvino as ov

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


@keras.utils.register_keras_serializable(package="Custom")
class TSM(keras.layers.Layer):
    """Minimal TSM layer stub to load MTTS-CAN HDF5.

    We only need this to deserialize the original Keras model so that
    OpenVINO can convert it; no runtime behavior is required here.
    """

    def __init__(self, n_frame=10, fold_div=3, **kwargs):
        super().__init__(**kwargs)
        self.n_frame = n_frame
        self.fold_div = fold_div

    def call(self, inputs, *args, **kwargs):  # pragma: no cover - conversion helper
        return inputs

    def get_config(self):
        config = super().get_config()
        config.update({"n_frame": self.n_frame, "fold_div": self.fold_div})
        return config


@keras.utils.register_keras_serializable(package="Custom")
class Attention_mask(keras.layers.Layer):
    """Minimal Attention_mask stub for MTTS-CAN loading."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def call(self, inputs, *args, **kwargs):  # pragma: no cover - conversion helper
        if isinstance(inputs, list) and len(inputs) == 2:
            attention, features = inputs
            attention = tf.repeat(attention, features.shape[-1], axis=-1)
            return attention * features
        return inputs

    def get_config(self):
        return super().get_config()


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


def convert_model_to_openvino() -> None:
    """Convert MTTS-CAN HDF5 model to OpenVINO IR for Intel iGPU.

    Produces /models/rppg/mtts_can.xml and .bin, which will be used by the
    rPPG service running on GPU.
    """

    h5_path = Path("/models") / "rppg" / "mtts_can.hdf5"
    xml_path = Path("/models") / "rppg" / "mtts_can.xml"

    if not h5_path.exists():
        logger.error(f"Cannot convert to OpenVINO IR; HDF5 model missing: {h5_path}")
        return

    if xml_path.exists():
        logger.info(f"OpenVINO IR already exists: {xml_path}")
        return

    logger.info("Converting MTTS-CAN HDF5 model to OpenVINO IR (GPU-ready)...")

    # Load original Keras model with custom layers
    keras_model = keras.models.load_model(
        str(h5_path),
        custom_objects={"TSM": TSM, "Attention_mask": Attention_mask},
        compile=False,
    )

    # Convert to OpenVINO Model and save as IR
    ov_model = ov.convert_model(keras_model)
    ov.save_model(ov_model, str(xml_path))

    logger.info(f"✓ OpenVINO IR saved to {xml_path} (and corresponding .bin)")


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
            convert_model_to_openvino()
        elif args.video_only:
            download_video()
        else:
            download_model()
            convert_model_to_openvino()
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
