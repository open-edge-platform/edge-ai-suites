import logging, os, subprocess
from pathlib import Path
from typing import Tuple
import yaml
from utils.config_loader import config
from utils.cli_utils import run_cli
from utils.convert_classification_models import convert_classification_models
from utils.convert_yolo_models import convert_yolo_models

logger = logging.getLogger(__name__)
from huggingface_hub import snapshot_download

HF_PYTORCH_WEIGHTS_NAME = "pytorch_model.bin"

def _download_hf_model(
    model_name: str,
    output_dir: str,
    hf_token: str = None,
    force: bool = False,
    required_files: list[str] | None = None
) -> Tuple[bool, str]:
    """Download a HuggingFace model locally (full snapshot, offline usable)."""

    os.makedirs(output_dir, exist_ok=True)

    required_files = required_files or []
    has_required_files = all(
        os.path.exists(os.path.join(output_dir, required_file))
        for required_file in required_files
    )

    # If already downloaded and not forcing, reuse
    if not force and os.listdir(output_dir) and has_required_files:
        logger.info(f"⚡ Using cached HF model at {output_dir}")
        return True, output_dir

    if os.listdir(output_dir) and not has_required_files:
        logger.warning(f"Incomplete HF model cache detected at {output_dir}. Re-downloading snapshot.")

    logger.info(f"🚀 Downloading HF model {model_name} → {output_dir}\n"
                "⏳ This may take time depending on model size...\n"
                "⚠️ Please do not terminate.")

    try:
        snapshot_download(
            repo_id=model_name,
            local_dir=output_dir,
            local_dir_use_symlinks=False,   # important for portability (Docker etc.)
            token=hf_token
        )
    except Exception as e:
        logger.error(f"❌ HF download failed: {e}")
        return False, output_dir

    success = len(os.listdir(output_dir)) > 0
    logger.info("✅ Download successful" if success else "❌ Download incomplete")
    return success, output_dir

def _cache_diarization_dependencies_locally(pipeline_dir: str, hf_token: str = None) -> None:
    config_path = os.path.join(pipeline_dir, "config.yaml")
    if not os.path.exists(config_path):
        return

    with open(config_path, "r", encoding="utf-8") as handle:
        pipeline_config = yaml.safe_load(handle) or {}

    pipeline_params = pipeline_config.get("pipeline", {}).get("params", {})
    changed = False

    for key in ("segmentation", "embedding"):
        model_ref = pipeline_params.get(key)
        if not isinstance(model_ref, str):
            continue
        if os.path.isfile(model_ref):
            continue
        if "/" not in model_ref:
            continue

        dependency_dir = os.path.join(pipeline_dir, "dependencies", model_ref.replace("/", "_"))
        success, _ = _download_hf_model(
            model_ref,
            dependency_dir,
            hf_token=hf_token,
            required_files=[HF_PYTORCH_WEIGHTS_NAME, "config.yaml"]
        )
        if not success:
            continue

        checkpoint_path = os.path.join(dependency_dir, HF_PYTORCH_WEIGHTS_NAME)
        if os.path.exists(checkpoint_path):
            pipeline_params[key] = checkpoint_path
            changed = True

    if changed:
        with open(config_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(pipeline_config, handle, sort_keys=False)

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
    if config.models.diarization.provider == "huggingface":
        output_dir = get_diarization_model_path()
        success, _ = _download_hf_model(
            config.models.diarization.name,
            output_dir,
            hf_token=config.models.asr.hf_token,
            required_files=["config.yaml"]
        )
        if success:
            _cache_diarization_dependencies_locally(output_dir, hf_token=config.models.asr.hf_token)
    
    output_dir = get_va_model_path()
    convert_yolo_models(output_dir, [config.models.va.front_pose_model, config.models.va.back_pose_model])
    convert_classification_models(output_dir)
    
    if config.models.ocr.enabled:
        _initialize_ocr()


def _initialize_ocr():
    from utils.ocr_utils.paddle_model_manager import PaddleOCRModelManager
    from utils.ocr_utils.convert_to_openvino import convert_ppocr_pipeline
    
    # Suppress PyTorch warning when loading PaddleOCR .pdmodel files
    logging.getLogger("torch.export.pt2_archive._package").setLevel(logging.ERROR)
    
    lang = config.app.language
    if lang != "en":
        raise RuntimeError(
            f"OCR currently only supports English (lang='en'). Got: '{lang}'. "
            f"To use other languages, set 'ocr.enabled: false' in config.yaml."
        )
    
    logger.info(f"Initializing OCR models: provider={config.models.ocr.provider}, lang={lang}, device={config.models.ocr.device}")
    PaddleOCRModelManager.initialize(lang=lang, use_angle_cls=True, device=config.models.ocr.device)
    
    if config.models.ocr.provider == "openvino":
        paddle_models_dir = Path(config.models.ocr.model_dir)
        lang = config.app.language
        det_dir = paddle_models_dir / "det" / lang
        rec_dir = paddle_models_dir / "rec" / lang
        
        if not det_dir.exists() or not any(det_dir.iterdir()):
            raise RuntimeError(
                f"{paddle_models_dir}/det/{lang}/ is empty. Ensure PaddleOCR models are cached before initializing OpenVINO OCR."
            )
        if not rec_dir.exists() or not any(rec_dir.iterdir()):
            raise RuntimeError(
                f"{paddle_models_dir}/rec/{lang}/ is empty. Ensure PaddleOCR models are cached before initializing OpenVINO OCR."
            )
        
        logger.info("Converting PaddleOCR models to OpenVINO IR...")
        convert_ppocr_pipeline(models_root=paddle_models_dir, output_root=paddle_models_dir, lang=lang)
        logger.info("OpenVINO IR conversion completed")


def get_model_path() -> str:
    return os.path.join(config.models.summarizer.models_base_path, config.models.summarizer.provider, f"{config.models.summarizer.name.replace('/', '_')}_{config.models.summarizer.weight_format}")

def get_asr_model_path() -> str:
    return os.path.join(config.models.asr.models_base_path, config.models.asr.provider, f"{config.models.asr.name.replace('/', '_')}")

def get_va_model_path() -> str:
    return os.path.join(config.models.va.models_base_path, "va")

def get_diarization_model_path() -> str:
    return os.path.join(
        config.models.diarization.models_base_path,
        config.models.diarization.provider,
        config.models.diarization.name.replace('/', '_')
    )
