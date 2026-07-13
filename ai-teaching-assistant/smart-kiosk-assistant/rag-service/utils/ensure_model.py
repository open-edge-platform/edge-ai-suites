from __future__ import annotations

import logging
import os
import shutil

from huggingface_hub import snapshot_download
from optimum.exporters.openvino import main_export

from utils.config_loader import config


logger = logging.getLogger(__name__)
_WEIGHT_FORMATS = {"fp32", "fp16", "int8", "int4"}
_SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _slugify(model_name: str, suffix: str | None = None) -> str:
    slug = model_name.replace("/", "_")
    return f"{slug}__{suffix}" if suffix else slug


def _resolve_service_path(path: str) -> str:
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(_SERVICE_ROOT, path))


def _llm_model_exists(output_dir: str) -> bool:
    xml_path = os.path.join(output_dir, "openvino_model.xml")
    bin_path = os.path.join(output_dir, "openvino_model.bin")
    return (
        os.path.isfile(xml_path)
        and os.path.getsize(xml_path) > 0
        and os.path.isfile(bin_path)
        and os.path.getsize(bin_path) > 0
    )


def _llm_tokenizer_exists(output_dir: str) -> bool:
    required = (
        "openvino_tokenizer.xml",
        "openvino_tokenizer.bin",
        "openvino_detokenizer.xml",
        "openvino_detokenizer.bin",
    )
    return all(
        os.path.isfile(os.path.join(output_dir, name))
        and os.path.getsize(os.path.join(output_dir, name)) > 0
        for name in required
    )


def _llm_export_ready(output_dir: str) -> bool:
    return _llm_model_exists(output_dir) and _llm_tokenizer_exists(output_dir)


def _download_repo(repo_id: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=output_dir,
        local_dir_use_symlinks=False,
    )
    return output_dir


def _reset_output_dir(output_dir: str) -> None:
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)


def _export_openvino_tokenizer(model_name: str, output_dir: str) -> None:
    try:
        from openvino import save_model
        from openvino_tokenizers import convert_tokenizer
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Tokenizer export dependencies are not available. Install OpenVINO tokenizer conversion support."
        ) from exc

    logger.info("Exporting tokenizer IR for %s into %s", model_name, output_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    converted = convert_tokenizer(tokenizer, with_detokenizer=True)
    if isinstance(converted, tuple):
        ov_tokenizer, ov_detokenizer = converted
    else:
        ov_tokenizer = converted
        ov_detokenizer = None

    save_model(ov_tokenizer, os.path.join(output_dir, "openvino_tokenizer.xml"))
    if ov_detokenizer is not None:
        save_model(ov_detokenizer, os.path.join(output_dir, "openvino_detokenizer.xml"))

    if not _llm_tokenizer_exists(output_dir):
        raise RuntimeError(
            f"Tokenizer export failed for {model_name}: OpenVINO tokenizer IR is incomplete in {output_dir}"
        )


def _export_openvino_model(
    model_name: str,
    output_dir: str,
    weight_format: str,
    task: str | None = None,
) -> str:
    if weight_format not in _WEIGHT_FORMATS:
        raise ValueError(f"Unsupported OpenVINO weight format: {weight_format}")

    _reset_output_dir(output_dir)
    logger.info(
        "Exporting %s → %s via main_export (task=%s, weight_format=%s)",
        model_name,
        output_dir,
        task or "text-generation-with-past",
        weight_format,
    )
    main_export(
        model_name_or_path=model_name,
        output=output_dir,
        task=task or "text-generation-with-past",
        trust_remote_code=True,
        weight_format=weight_format,
    )
    if not _llm_model_exists(output_dir):
        raise RuntimeError(
            f"OpenVINO export failed for {model_name}: main_export did not produce a valid IR in {output_dir}"
        )
    _export_openvino_tokenizer(model_name, output_dir)
    return output_dir


def get_llm_model_path() -> str:
    llm_cfg = config.models.llm
    return os.path.join(
        _resolve_service_path(llm_cfg.models_base_path),
        _slugify(llm_cfg.hf_id, getattr(llm_cfg, "weight_format", "int8")),
    )


def get_embedding_model_path() -> str:
    emb_cfg = config.models.embedding
    return os.path.join(
        _resolve_service_path(emb_cfg.models_base_path),
        "sentence_transformers",
        _slugify(emb_cfg.hf_id),
    )


def get_embedding_openvino_path() -> str:
    emb_cfg = config.models.embedding
    weight_format = getattr(emb_cfg, "weight_format", "fp32") or "fp32"
    return os.path.join(
        _resolve_service_path(emb_cfg.models_base_path),
        "openvino",
        _slugify(emb_cfg.hf_id, weight_format),
    )


def _ov_export_ready(output_dir: str) -> bool:
    xml = os.path.join(output_dir, "openvino_model.xml")
    binp = os.path.join(output_dir, "openvino_model.bin")
    return (
        os.path.isfile(xml)
        and os.path.getsize(xml) > 0
        and os.path.isfile(binp)
        and os.path.getsize(binp) > 0
    )


def ensure_embedding_openvino(force: bool = False) -> str:
    emb_cfg = config.models.embedding
    weight_format = getattr(emb_cfg, "weight_format", "fp32") or "fp32"
    output_dir = get_embedding_openvino_path()
    if not force and _ov_export_ready(output_dir):
        logger.info("Using cached OpenVINO embedding export at %s", output_dir)
        return output_dir
    logger.info(
        "Exporting %s → OpenVINO IR at %s (task=feature-extraction, weight_format=%s)",
        emb_cfg.hf_id, output_dir, weight_format,
    )
    _reset_output_dir(output_dir)
    main_export(
        model_name_or_path=emb_cfg.hf_id,
        output=output_dir,
        task="feature-extraction",
        trust_remote_code=True,
        weight_format=weight_format,
    )
    if not _ov_export_ready(output_dir):
        raise RuntimeError(
            f"OpenVINO export failed for {emb_cfg.hf_id}: no valid IR in {output_dir}"
        )
    return output_dir


def ensure_llm_model(force: bool = False) -> str:
    llm_cfg = config.models.llm
    output_dir = get_llm_model_path()
    hf_id = llm_cfg.hf_id

    if not force and _llm_export_ready(output_dir):
        logger.info("Using cached OpenVINO LLM export at %s", output_dir)
        return output_dir

    if not force and _llm_model_exists(output_dir) and not _llm_tokenizer_exists(output_dir):
        logger.info("Repairing missing tokenizer IR for cached OpenVINO LLM export at %s", output_dir)
        _export_openvino_tokenizer(hf_id, output_dir)
        logger.info("LLM ready at %s", output_dir)
        return output_dir

    weight_format = getattr(llm_cfg, "weight_format", "int8")
    logger.info(
        "Exporting %s → OpenVINO IR at %s (weight_format=%s). "
        "This takes a few minutes on first run.",
        hf_id, output_dir, weight_format,
    )
    _export_openvino_model(hf_id, output_dir, weight_format)

    if not _llm_export_ready(output_dir):
        raise RuntimeError(
            f"LLM model export completed but required OpenVINO artifacts are missing from {output_dir}"
        )
    logger.info("LLM ready at %s", output_dir)
    return output_dir


def ensure_embedding_model(force: bool = False) -> str:
    emb_cfg = config.models.embedding
    output_dir = get_embedding_model_path()
    if not force and os.path.isdir(output_dir) and any(os.scandir(output_dir)):
        logger.info("Using cached embedding model at %s", output_dir)
        return output_dir

    logger.info("Downloading sentence-transformers embedding model %s to %s", emb_cfg.hf_id, output_dir)
    _download_repo(emb_cfg.hf_id, output_dir)
    return output_dir


def ensure_model(force: bool = False) -> None:
    ensure_llm_model(force=force)
    emb_backend = (getattr(config.models.embedding, "backend", "") or "").lower()
    if emb_backend == "openvino":
        ensure_embedding_openvino(force=force)
    else:
        ensure_embedding_model(force=force)
    reranker_cfg = getattr(config.retrieval, "reranker", None)
    if reranker_cfg is not None and bool(getattr(reranker_cfg, "enabled", False)):
        rr_backend = (getattr(reranker_cfg, "backend", "") or "").lower()
        if rr_backend == "openvino":
            ensure_reranker_openvino(force=force)
        else:
            ensure_reranker_model(force=force)


def resolve_embedding_model_source() -> str:
    emb_cfg = config.models.embedding
    output_dir = get_embedding_model_path()
    if os.path.isdir(output_dir) and any(os.scandir(output_dir)):
        return output_dir
    return emb_cfg.hf_id


def get_reranker_model_path() -> str:
    reranker_cfg = config.retrieval.reranker
    base_path = getattr(reranker_cfg, "models_base_path", "./models/rerankers")
    return os.path.join(
        _resolve_service_path(base_path),
        "sentence_transformers",
        _slugify(reranker_cfg.hf_id),
    )


def get_reranker_openvino_path() -> str:
    reranker_cfg = config.retrieval.reranker
    base_path = getattr(reranker_cfg, "models_base_path", "./models/rerankers")
    weight_format = getattr(reranker_cfg, "weight_format", "fp32") or "fp32"
    return os.path.join(
        _resolve_service_path(base_path),
        "openvino",
        _slugify(reranker_cfg.hf_id, weight_format),
    )


def ensure_reranker_openvino(force: bool = False) -> str:
    reranker_cfg = config.retrieval.reranker
    weight_format = getattr(reranker_cfg, "weight_format", "fp32") or "fp32"
    output_dir = get_reranker_openvino_path()
    if not force and _ov_export_ready(output_dir):
        logger.info("Using cached OpenVINO reranker export at %s", output_dir)
        return output_dir
    logger.info(
        "Exporting %s → OpenVINO IR at %s (task=text-classification, weight_format=%s)",
        reranker_cfg.hf_id, output_dir, weight_format,
    )
    _reset_output_dir(output_dir)
    main_export(
        model_name_or_path=reranker_cfg.hf_id,
        output=output_dir,
        task="text-classification",
        trust_remote_code=True,
        weight_format=weight_format,
    )
    if not _ov_export_ready(output_dir):
        raise RuntimeError(
            f"OpenVINO export failed for {reranker_cfg.hf_id}: no valid IR in {output_dir}"
        )
    return output_dir


def ensure_reranker_model(force: bool = False) -> str:
    reranker_cfg = config.retrieval.reranker
    output_dir = get_reranker_model_path()
    if not force and os.path.isdir(output_dir) and any(os.scandir(output_dir)):
        logger.info("Using cached reranker model at %s", output_dir)
        return output_dir

    logger.info("Downloading cross-encoder reranker model %s to %s", reranker_cfg.hf_id, output_dir)
    _download_repo(reranker_cfg.hf_id, output_dir)
    return output_dir


def resolve_reranker_model_source() -> str:
    reranker_cfg = config.retrieval.reranker
    output_dir = get_reranker_model_path()
    if os.path.isdir(output_dir) and any(os.scandir(output_dir)):
        return output_dir
    return reranker_cfg.hf_id
