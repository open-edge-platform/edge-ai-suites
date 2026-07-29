"""Convert MTTS-CAN HDF5 model to OpenVINO IR format.

Reads the source HDF5 path and output directory from model-config.yaml
(rppg.models[0].source_model_path and rppg.models[0].target_dir).

Skips conversion if both IR artifacts (XML + BIN) already exist (idempotent).

Runs inside the nicu-rppg-converter container (make convert-rppg), which mounts:
  - ./configs/model-config.yaml -> /app/configs/model-config.yaml
  - ./models_rppg             -> /models/rppg
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path("/app/configs/model-config.yaml")


def _load_config(config_path: Path) -> tuple[Path, Path]:
    """Return (source_hdf5_path, output_xml_path) from model-config.yaml."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found: {config_path}. "
            "Ensure model-config.yaml is mounted at /app/configs/model-config.yaml."
        )
    with config_path.open("r") as f:
        cfg = yaml.safe_load(f) or {}

    rppg_cfg = cfg.get("rppg", {})
    models = rppg_cfg.get("models", [])
    if not models:
        raise ValueError("model-config.yaml has no rppg.models entries.")

    m = models[0]
    source_model_path = m.get("source_model_path")
    target_dir = m.get("target_dir")
    if not source_model_path or not target_dir:
        raise ValueError(
            "rppg.models[0] must define source_model_path and target_dir."
        )

    return Path(source_model_path), Path(target_dir) / "mtts_can.xml"


def _resolve_source_hdf5(configured_source: Path, output_xml: Path) -> Path:
    """Resolve source HDF5 with fallback to any single .hdf5 in target dir.

    Users may place the HDF5 model with a different filename. Prefer the
    configured source_model_path; fall back to detecting exactly one .hdf5
    file in the output directory.
    """
    if configured_source.exists():
        return configured_source

    target_dir = output_xml.parent
    candidates = sorted(target_dir.glob("*.hdf5"))
    if len(candidates) == 1:
        logger.info(
            "Configured HDF5 not found at %s. Using detected: %s",
            configured_source,
            candidates[0],
        )
        return candidates[0]

    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise FileNotFoundError(
            f"Configured HDF5 not found at {configured_source}. "
            f"Multiple .hdf5 files found in {target_dir}: {names}. "
            "Keep only one or set rppg.models[0].source_model_path explicitly."
        )

    raise FileNotFoundError(
        f"HDF5 model not found: {configured_source}. "
        f"Place your .hdf5 file in {target_dir} before running conversion."
    )


def convert(source_hdf5: Path, output_xml: Path) -> None:
    """Convert HDF5 Keras model to OpenVINO IR. No-op if both IR artifacts exist."""
    output_bin = output_xml.with_suffix(".bin")
    if output_xml.exists() and output_bin.exists():
        logger.info(
            "OpenVINO IR already exists: %s and %s — skipping conversion.",
            output_xml,
            output_bin,
        )
        return

    if not source_hdf5.exists():
        raise FileNotFoundError(
            f"HDF5 model not found: {source_hdf5}. "
            "Place the .hdf5 file in models_rppg/ before running."
        )

    import tensorflow as tf
    from tensorflow import keras

    @keras.utils.register_keras_serializable(package="Custom")
    class TSM(keras.layers.Layer):
        """Temporal Shift Module stub needed only for HDF5 deserialization."""

        def __init__(self, n_frame: int = 10, fold_div: int = 3, **kwargs):
            super().__init__(**kwargs)
            self.n_frame = n_frame
            self.fold_div = fold_div

        def call(self, inputs, *args, **kwargs):
            return inputs

        def get_config(self):
            cfg = super().get_config()
            cfg.update({"n_frame": self.n_frame, "fold_div": self.fold_div})
            return cfg

    @keras.utils.register_keras_serializable(package="Custom")
    class Attention_mask(keras.layers.Layer):
        """Attention mask stub needed only for HDF5 deserialization."""

        def call(self, inputs, *args, **kwargs):
            if isinstance(inputs, list) and len(inputs) == 2:
                attention, features = inputs
                attention = tf.repeat(attention, features.shape[-1], axis=-1)
                return attention * features
            return inputs

        def get_config(self):
            return super().get_config()

    logger.info("Loading MTTS-CAN HDF5 model from %s ...", source_hdf5)
    keras_model = keras.models.load_model(
        str(source_hdf5),
        custom_objects={"TSM": TSM, "Attention_mask": Attention_mask},
        compile=False,
    )
    logger.info(
        "Model loaded: inputs=%s outputs=%s",
        [i.shape for i in keras_model.inputs],
        [o.shape for o in keras_model.outputs],
    )

    import openvino as ov

    output_xml.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Converting to OpenVINO IR ...")
    ov_model = ov.convert_model(keras_model)
    ov.save_model(ov_model, str(output_xml))

    logger.info("Saved: %s (%d KB)", output_xml, output_xml.stat().st_size // 1024)
    logger.info("Saved: %s (%d KB)", output_bin, output_bin.stat().st_size // 1024)
    logger.info("Conversion complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert MTTS-CAN HDF5 to OpenVINO IR")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to model-config.yaml",
    )
    parser.add_argument("--input", default=None, help="Path to HDF5 model (overrides config)")
    parser.add_argument("--output", default=None, help="Path to output XML (overrides config)")
    args = parser.parse_args()

    try:
        if args.input and args.output:
            configured_source = Path(args.input)
            output_xml = Path(args.output)
        else:
            configured_source, output_xml = _load_config(Path(args.config))

        source_hdf5 = _resolve_source_hdf5(configured_source, output_xml)
        convert(source_hdf5, output_xml)
    except Exception as exc:
        logger.error("Conversion failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
