import logging
from pathlib import Path
from os import PathLike
from typing import Optional

import openvino as ov
from openvino import save_model
from utils.config_loader import config

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

PADDLEOCR_DICT_URLS = {
    "en": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/v2.7.0/ppocr/utils/en_dict.txt",
    "ch": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/v2.7.0/ppocr/utils/ppocr_keys_v1.txt",
    "chinese_cht": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/v2.7.0/ppocr/utils/ppocr_keys_v1.txt",
}

def download_file(
    url: PathLike,
    filename: PathLike = None,
    directory: PathLike = None,
    chunk_size: int = 16384
) -> PathLike:
    import requests
    import urllib.parse
    
    filename = filename or Path(urllib.parse.urlparse(url).path).name
    filename = Path(filename)
    filepath = Path(directory) / filename if directory is not None else filename
    
    # Return existing file
    if filepath.exists():
        log.info(f"File already exists: {filepath}")
        return filepath.resolve()
    
    if directory is not None:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    log.info(f"Downloading: {url}")
    log.info(f"Output: {filepath}")
    
    try:
        response = requests.get(
            url=url,
            headers={"User-agent": "Mozilla/5.0"},
            stream=True,
            timeout=30
        )
        response.raise_for_status()
        
    except requests.exceptions.HTTPError as error:
        log.error(f"HTTP error: {error}")
        raise Exception(f"HTTP error: {error}") from None
    except requests.exceptions.Timeout:
        log.error("Connection timed out")
        raise Exception(
            "Connection timed out. If you access the internet through a proxy server, "
            "please make sure the proxy is set correctly."
        ) from None
    except requests.exceptions.RequestException as error:
        log.error(f"Request failed: {error}")
        raise Exception(f"File downloading failed with error: {error}") from None
    
    # Write file
    with open(filepath, "wb") as file_object:
        for chunk in response.iter_content(chunk_size):
            file_object.write(chunk)
    
    response.close()
    log.info(f"Download complete: {filepath}")
    
    return filepath.resolve()


def download_char_dict(
    lang: str = None,
    output_dir: Path = None,
    force: bool = False
) -> Path:
    import requests
    
    lang = config.models.ocr
    
    if output_dir is None:
        output_dir = Path(config.models.ocr.model_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"ppocrv4_{lang}_chars.txt"
    
    if output_file.exists() and not force:
        line_count = sum(1 for _ in open(output_file, 'r', encoding='utf-8'))
        if line_count >= 50:
            log.info(f"Character dictionary already exists: {output_file} ({line_count} chars)")
            return output_file
        else:
            log.warning(f"Existing dictionary is corrupted ({line_count} chars), re-downloading...")
    
    url = PADDLEOCR_DICT_URLS.get(lang)
    if not url:
        log.warning(f"No dictionary URL for language '{lang}', falling back to English")
        url = PADDLEOCR_DICT_URLS["en"]
    
    log.info(f"Downloading PaddleOCR character dictionary for '{lang}'...")
    log.info(f"URL: {url}")
    log.info(f"Output: {output_file}")
    
    try:
        response = requests.get(
            url=url,
            headers={"User-agent": "Mozilla/5.0"},
            timeout=30
        )
        response.raise_for_status()
        content = response.text
        response.close()
        
    except requests.exceptions.HTTPError as error:
        log.error(f"HTTP error downloading dictionary: {error}")
        raise RuntimeError(f"Failed to download character dictionary: HTTP error {error}")
    except requests.exceptions.Timeout:
        log.error("Timeout downloading character dictionary")
        raise RuntimeError(
            "Connection timed out. If you access the internet through a proxy server, "
            "please make sure the proxy is set correctly."
        )
    except requests.exceptions.RequestException as error:
        log.error(f"Request failed: {error}")
        raise RuntimeError(f"Failed to download character dictionary: {error}")
    
    lines = content.strip().split('\n')
    if len(lines) < 50:
        log.error(f"Downloaded dictionary has too few characters ({len(lines)})")
        raise RuntimeError(f"Downloaded dictionary has too few characters ({len(lines)})")
    
    if lines[0].strip() != 'blank':
        lines.insert(0, 'blank')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    log.info(f"Successfully downloaded character dictionary: {len(lines)} characters")
    return output_file


def _find_pdmodel(model_dir: Path) -> Path:
    """Return the .pdmodel file inside *model_dir* (raises if not found)."""
    candidates = list(model_dir.glob("*.pdmodel"))
    if not candidates:
        raise FileNotFoundError(
            f"No .pdmodel file found in '{model_dir}'. "
            "Make sure you downloaded the *_infer.tar.gz archive and extracted it."
        )
    if len(candidates) > 1:
        log.warning("Multiple .pdmodel files found; using '%s'.", candidates[0])
    return candidates[0]


def convert_model(
    pdmodel_path: Path,
    output_dir: Path,
    model_name: str = None,
    dynamic_width: bool = False,
) -> tuple:

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = model_name or pdmodel_path.stem
    xml_path = output_dir / f"{stem}.xml"
    bin_path = output_dir / f"{stem}.bin"

    log.info("Reading model: %s", pdmodel_path)
    ov_model = ov.convert_model(str(pdmodel_path))


    if dynamic_width:
        for inp in ov_model.inputs:
            shape = inp.partial_shape
            if shape.rank.is_static and shape.rank.get_length() == 4:
                shape[3] = -1      
                ov_model.reshape({inp: shape})
                log.info(
                    "  Applied dynamic width on input '%s': %s",
                    inp.any_name,
                    shape,
                )

    log.info("Saving IR model → %s", xml_path)
    save_model(ov_model, str(xml_path), compress_to_fp16=False)

    log.info("Done: %s  |  %s", xml_path.name, bin_path.name)
    return xml_path, bin_path


def convert_ppocr_pipeline(
    models_root: Path,
    output_root: Path,
    det_dir: str = None,
    rec_dir: str = None,
    cls_dir: str = None,
    lang: str = None,
) -> dict:

    lang = lang or config.app.language
    det_dir = det_dir or config.models.ocr.det_model
    rec_dir = rec_dir or config.models.ocr.rec_model
    cls_dir = cls_dir if cls_dir is not None else config.models.ocr.cls_model
    
    results = {}

    det_path = models_root / "det" / lang / det_dir
    if det_path.exists():
        det_pdmodel = _find_pdmodel(det_path)
        results["det"] = convert_model(
            pdmodel_path=det_pdmodel,
            output_dir=output_root / "det" / lang / det_dir,
            model_name="det_model",
            dynamic_width=False,
        )
        log.info("Detection model saved to: %s/det/%s/%s/", output_root, lang, det_dir)
    else:
        log.warning("Detection model dir not found: %s", det_path)

    rec_path = models_root / "rec" / lang / rec_dir
    if rec_path.exists():
        rec_pdmodel = _find_pdmodel(rec_path)
        results["rec"] = convert_model(
            pdmodel_path=rec_pdmodel,
            output_dir=output_root / "rec" / lang / rec_dir,
            model_name="rec_model",
            dynamic_width=True, 
        )
        log.info("Recognition model saved to: %s/rec/%s/%s/", output_root, lang, rec_dir)
    else:
        log.warning("Recognition model dir not found: %s", rec_path)

    if cls_dir:
        cls_path = models_root / "cls" / cls_dir
        if cls_path.exists():
            cls_pdmodel = _find_pdmodel(cls_path)
            results["cls"] = convert_model(
                pdmodel_path=cls_pdmodel,
                output_dir=output_root / "cls" / cls_dir,
                model_name="cls_model",
                dynamic_width=False,
            )
            log.info("Classification model saved to: %s/cls/%s/", output_root, cls_dir)
        else:
            log.warning("Classification model dir not found, skipping: %s", cls_path)

    return results

def verify_ir(xml_path: Path, device: str = "CPU") -> None:
    core = ov.Core()
    model = core.read_model(str(xml_path))
    compiled = core.compile_model(model, device_name=device)

    log.info("=== Verification: %s ===", xml_path.name)
    for inp in compiled.inputs:
        log.info("  Input  : name=%s  shape=%s  dtype=%s",
                 inp.any_name, inp.partial_shape, inp.element_type)
    for out in compiled.outputs:
        log.info("  Output : name=%s  shape=%s  dtype=%s",
                 out.any_name, out.partial_shape, out.element_type)
