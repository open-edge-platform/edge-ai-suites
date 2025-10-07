import logging, os
from typing import Tuple
from utils.config_loader import config
from utils.cli_utils import run_cli
logger = logging.getLogger(__name__)

def _ir_exists(output_dir: str) -> bool:
    """Check if exported OpenVINO IR files exist."""
    xml_file = os.path.join(output_dir, "openvino_model.xml")
    bin_file = os.path.join(output_dir, "openvino_model.bin")
    en_xml_file = os.path.join(output_dir, "openvino_encoder_model.xml")
    en_bin_file = os.path.join(output_dir, "openvino_encoder_model.bin")
    de_xml_file = os.path.join(output_dir, "openvino_decoder_model.xml")
    de_bin_file = os.path.join(output_dir, "openvino_decoder_model.bin")
    return (os.path.exists(xml_file) and os.path.exists(bin_file)) or (os.path.exists(en_xml_file) and os.path.exists(en_bin_file) and os.path.exists(de_xml_file) and os.path.exists(de_bin_file))

def _download_openvino_model(
    model_name: str,
    output_dir: str,
    weight_format: str,
    force: bool = False
) -> Tuple[bool, str]:
    """Export a HuggingFace model to OpenVINO IR using optimum-cli."""
    os.makedirs(output_dir, exist_ok=True)

    if not force and _ir_exists(output_dir):
        logger.info(f"⚡ Using cached export at {output_dir}")
        return True, output_dir

    cmd = [
        "optimum-cli", "export", "openvino",
        "--model", model_name,
        "--trust-remote-code",
        output_dir,
    ] + (["--weight-format", weight_format] if weight_format else [])

    logger.info(f"🚀  Exporting {model_name} → {output_dir} ({weight_format})\n"
                "⏳  Exporting model... This process may take some time depending on the model size. \n"
                "⚠️  Please do not terminate the process.")

    return_code = run_cli(cmd=cmd, log_fn=logger.info)
    if return_code != 0:
        logger.error(f"❌ Export failed: {return_code}")
        return False, output_dir

    success = _ir_exists(output_dir)
    logger.info("✅ Export successful" if success else "❌ Export incomplete")
    return success, output_dir

def ensure_model():
    if config.models.summarizer.provider == "openvino":
        output_dir = get_model_path()
        _download_openvino_model(config.models.summarizer.name, output_dir, config.models.summarizer.weight_format)
    if config.models.asr.provider == "openvino":
        output_dir = get_asr_model_path()
        _download_openvino_model(f"openai/{config.models.asr.name}", output_dir, None)

def get_model_path() -> str:
    return os.path.join(config.models.summarizer.models_base_path, config.models.summarizer.provider, f"{config.models.summarizer.name.replace('/', '_')}_{config.models.summarizer.weight_format}")

def get_asr_model_path() -> str:
    return os.path.join(config.models.asr.models_base_path, config.models.asr.provider, f"{config.models.asr.name.replace('/', '_')}")
