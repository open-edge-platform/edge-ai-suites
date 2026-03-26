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

import yaml
import tensorflow as tf
from tensorflow import keras
import openvino as ov

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


CONFIG_PATH = Path("/app/configs/model-config.yaml")


def _load_rppg_model_config() -> tuple[str, str, str, str, str]:
    """Load rPPG model and video settings from config.

    This function expects /app/configs/model-config.yaml to exist and to
    define rppg.models[0] with at least:

      - name
      - target_dir
      - model_url
      - video_dir
      - video_url

    If any of these are missing or the file is not readable, the script
    will raise and fail fast instead of using hardcoded defaults.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"rPPG config not found at {CONFIG_PATH}. Ensure model-config.yaml is mounted."
        )

    try:
        with CONFIG_PATH.open("r") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to parse rPPG config {CONFIG_PATH}: {e}") from e

    rppg_cfg = cfg.get("rppg", {})
    models = rppg_cfg.get("models", [])
    if not models:
        raise ValueError(
            "model-config.yaml has no rppg.models entries; please define at least one."
        )

    first = models[0] or {}
    name = first.get("name")
    target_dir = first.get("target_dir")
    model_url = first.get("model_url")
    video_dir = first.get("video_dir")
    video_url = first.get("video_url")

    if not name or not target_dir or not model_url or not video_dir or not video_url:
        raise ValueError(
            "rppg.models[0] must define name, target_dir, model_url, video_dir, "
            "and video_url in model-config.yaml."
        )

    return (
        str(name),
        str(target_dir),
        str(model_url),
        str(video_dir),
        str(video_url),
    )


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
    """Download MTTS-CAN model weights.

    The destination filename under /models/rppg is taken from
    model-config.yaml (rppg.models[0].name) and the download URL from
    rppg.models[0].model_url.
    """
    model_filename, target_dir, model_url, _, _ = _load_rppg_model_config()
    model_path = Path(target_dir) / model_filename

    if model_path.exists():
        logger.info(f"Model already exists: {model_path}")
        size_mb = model_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Size: {size_mb:.1f} MB")
        return

    logger.info("Downloading MTTS-CAN model...")
    logger.info(f"  Source: {model_url}")
    logger.info(f"  Destination: {model_path}")

    try:
        download_file(model_url, model_path, "Model")
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
    model_filename, target_dir, _, _, _ = _load_rppg_model_config()
    h5_path = Path(target_dir) / model_filename
    # Keep the IR filename stable; config controls input HDF5 name.
    xml_path = Path(target_dir) / "mtts_can.xml"

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
    """Download sample video.

    The destination directory and download URL are taken from
    model-config.yaml (rppg.models[0].video_dir and video_url).
    """
    _, _, _, video_dir, video_url = _load_rppg_model_config()
    video_path = Path(video_dir) / "sample.mp4"

    if video_path.exists():
        logger.info(f"Video already exists: {video_path}")
        size_mb = video_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Size: {size_mb:.1f} MB")
        return

    logger.info("Downloading sample video...")
    logger.info(f"  Source: {video_url}")
    logger.info(f"  Destination: {video_path}")

    try:
        download_file(video_url, video_path, "Video")
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
