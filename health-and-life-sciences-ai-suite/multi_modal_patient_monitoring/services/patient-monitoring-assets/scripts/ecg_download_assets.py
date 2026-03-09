#!/usr/bin/env python3
import logging
import sys
import urllib.request
from pathlib import Path

import yaml

BASE_URL = "https://raw.githubusercontent.com/Einse57/OpenVINO_sample/master/ai-ecg-master"
CONFIG_PATH = Path("/app/configs/model-config.yaml")


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def download_file(url: str, dest: Path, desc: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s -> %s", desc, dest)
    try:
        with urllib.request.urlopen(url) as resp, dest.open("wb") as f:
            f.write(resp.read())
    except Exception as e:
        logger.error("Failed to download %s from %s: %s", desc, url, e)
        raise


def load_ecg_models_from_config() -> list[tuple[Path, str, str, str]]:
    """Load ECG model directories and filenames from model-config.yaml.

    Returns a list of tuples: (target_dir, xml_filename, bin_filename, model_url).
    This function expects /app/configs/model-config.yaml to exist and to
    define ai-ecg.models[*] entries with at least target_dir and
    ir_file or name. If the file is missing or malformed, it will
    raise instead of silently using hardcoded defaults.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"ECG config not found at {CONFIG_PATH}. Ensure model-config.yaml is mounted."
        )

    try:
        data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to parse ECG config {CONFIG_PATH}: {e}") from e

    ai_ecg_cfg = data.get("ai-ecg", {})
    models = ai_ecg_cfg.get("models", [])
    if not models:
        raise ValueError(
            "model-config.yaml has no ai-ecg.models entries; please define at least one."
        )

    result: list[tuple[Path, str, str]] = []
    for m in models:
        m = m or {}
        target_dir_val = m.get("target_dir")
        ir_file_val = m.get("ir_file")
        name_val = m.get("name")
        model_url_val = m.get("model_url")

        if not target_dir_val:
            raise ValueError(
                "Each ai-ecg.models entry must define target_dir in model-config.yaml."
            )

        target_dir = Path(str(target_dir_val))

        # Prefer explicit ir_file; otherwise require name so we can derive
        # the IR filename as `<name>.xml`.
        if ir_file_val:
            xml_file = str(ir_file_val)
        else:
            if not name_val:
                raise ValueError(
                    "ai-ecg.models entries must define ir_file or name in model-config.yaml."
                )
            xml_file = f"{str(name_val).strip()}.xml"

        if not xml_file.endswith(".xml"):
            raise ValueError(
                f"ai-ecg model ir_file '{xml_file}' must be an .xml file."
            )

        bin_file = xml_file.replace(".xml", ".bin")

        # model_url is optional in config for backward compatibility; if
        # omitted, fall back to the legacy BASE_URL.
        if not model_url_val:
            logger.warning(
                "ai-ecg.models entry missing model_url; falling back to BASE_URL %s",
                BASE_URL,
            )
            model_url = BASE_URL
        else:
            model_url = str(model_url_val)

        result.append((target_dir, xml_file, bin_file, model_url))

    return result


def main() -> int:
    logger.info("ECG Asset Downloader starting")

    models = load_ecg_models_from_config()

    for target_dir, xml_name, bin_name, model_url in models:
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Using ECG model directory: %s", target_dir)

        for fname in (xml_name, bin_name):
            dest = target_dir / fname
            if dest.exists():
                logger.info("%s already exists, skipping", dest)
                continue

            url = f"{model_url}/{fname}"
            download_file(url, dest, fname)

    logger.info("ECG models ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
