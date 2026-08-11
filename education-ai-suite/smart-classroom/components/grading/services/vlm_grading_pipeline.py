from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from services.layout_detection import run_layout_detection
from services.pdf_render import render_pdf_to_pngs, image_info
from services.prompt_slicer import (
    append_common_output_suffix_if_missing,
    extract_header_block,
    prepend_common_prefix_if_missing,
    slice_prompt_for_section,
)
from services.reporter import build_result
from services.section_split import split_sections, _stitch, _stitch_compressed
from services.result_parser import merge_page_scores, parse_header_info, parse_scores
from services.vlm_client import check_health, extract_header_info, grade_page

ProgressCallback = Callable[[str, int], None]
CheckpointCallback = Callable[[str], bool]
LogCallback = Callable[[str], None]


def _component_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_component_config() -> dict[str, Any]:
    path = _component_root() / "config.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cfg = raw if isinstance(raw, dict) else {}
    except Exception:
        cfg = {}
    root = _component_root().parents[1] / "config.yaml"
    try:
        root_raw = yaml.safe_load(root.read_text(encoding="utf-8")) or {}
        cfg["_language"] = str((root_raw.get("app") or {}).get("language", "en"))
    except Exception:
        cfg["_language"] = "en"
    return cfg


def _load_provider_url(key: str, default: str) -> str:
    """Read a service URL from root config: grading.provider.<key>."""
    root = _component_root().parents[1] / "config.yaml"
    try:
        raw = yaml.safe_load(root.read_text(encoding="utf-8")) or {}
        provider = ((raw.get("grading") or {}).get("provider") or {})
        url = provider.get(key)
        if url:
            return str(url)
    except Exception:
        pass
    return default


def _outputs_dir(task_id: str, student_id: str | None) -> Path:
    return _component_root() / "outputs" / task_id / (student_id or "paper")


def run_vlm_grading_pipeline(
    task_id: str,
    request_payload: dict[str, Any],
    update_progress: ProgressCallback,
    check_checkpoint: CheckpointCallback,
    log_event: LogCallback | None = None,
) -> dict[str, Any]:
    def _log(message: str) -> None:
        if log_event is not None:
            log_event(message)

    timings: list[tuple[str, float]] = []

    def _step_start(step: str) -> float:
        _log(f"step {step} started")
        return time.perf_counter()

    def _step_done(step: str, started: float, extra: str = "") -> None:
        elapsed = time.perf_counter() - started
        timings.append((step, elapsed))
        suffix = f" {extra}" if extra else ""
        _log(f"step {step} completed elapsed={elapsed:.2f}s{suffix}")

    def _log_timing_summary(total: float) -> None:
        _log("timing summary:")
        for step, elapsed in timings:
            pct = (elapsed / total * 100) if total > 0 else 0.0
            _log(f"  {step:<18} {elapsed:>7.2f}s  {pct:>5.1f}%")
        _log(f"  {'TOTAL':<18} {total:>7.2f}s  100.0%")

    cfg = _load_component_config()
    cfg_image = cfg.get("image", {}) if isinstance(cfg.get("image"), dict) else {}
    cfg_vlm = cfg.get("vlm", {}) if isinstance(cfg.get("vlm"), dict) else {}
    cfg_grading = cfg.get("grading", {}) if isinstance(cfg.get("grading"), dict) else {}

    options = request_payload.get("options", {})
    if not isinstance(options, dict):
        options = {}

    paper_path = Path(str(request_payload["paper_path"])).resolve()
    student_id = request_payload.get("student_id")

    rubric_path = request_payload.get("rubric_path")
    if not rubric_path:
        raise ValueError("rubric_path is required")
    prompt_path = Path(str(rubric_path)).resolve()

    dpi = int(options.get("dpi", cfg_image.get("dpi", 300)))
    contrast_enhance = bool(cfg_image.get("contrast_enhance", False))
    contrast_factor = float(cfg_image.get("contrast_factor", 1.5))
    page_columns = int(cfg_image.get("page_columns", 1))
    column_split_ratio = float(cfg_image.get("column_split_ratio", 0.5))
    debug_mode = bool(cfg_grading.get("debug_mode", False))
    max_tokens = int(options.get("max_tokens", cfg_vlm.get("max_tokens", 4096)))
    temperature = float(options.get("temperature", cfg_vlm.get("temperature", 0.1)))
    _mip = options.get("max_image_pixels", cfg_vlm.get("max_image_pixels"))
    max_image_pixels = int(_mip) if _mip else None
    vlm_url = str(options.get("vlm_api_url") or _load_provider_url("vlm_provider", "http://127.0.0.1:9900"))
    layout_url = str(options.get("layout_detection_url") or _load_provider_url("layout_detection", "http://127.0.0.1:9902"))

    if not paper_path.exists():
        raise FileNotFoundError(f"paper (PDF) not found: {paper_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"grading prompt not found: {prompt_path}")

    user_prompt = prompt_path.read_text(encoding="utf-8")
    shared_rubrics_dir = _component_root() / "rubrics"
    prompt_with_prefix = prepend_common_prefix_if_missing(
        full_prompt=user_prompt,
        cfg=cfg.get("section_split", {}),
        language=cfg.get("_language", "en"),
        rubrics_dir=shared_rubrics_dir,
    )

    out_dir = _outputs_dir(task_id, student_id)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    _log(f"output base_dir={out_dir}")

    try:
        health = check_health(vlm_url)
        _log(f"vlm health ok model={health.get('model')} device={health.get('device')}")
    except Exception as exc:
        raise RuntimeError(f"VLM service unreachable at {vlm_url}: {exc}")

    _pipeline_start = time.perf_counter()
    update_progress("render", 20)
    _t = _step_start("render")
    images = render_pdf_to_pngs(paper_path, pages_dir, dpi=dpi,
                                contrast_enhance=contrast_enhance,
                                contrast_factor=contrast_factor,
                                page_columns=page_columns,
                                column_split_ratio=column_split_ratio)
    _step_done("render", _t, f"pages={len(images)} dpi={dpi} columns={page_columns}")
    if not images:
        raise RuntimeError("PDF produced no pages")

    if check_checkpoint("after_render"):
        _log("checkpoint stop after_render")
        return {"stopped": True}

    update_progress("layout_detection", 40)
    _t = _step_start("layout_detection")
    step1_dir = out_dir / "step1_layout_detection"
    det_summary = run_layout_detection(
        page_images=images,
        step1_dir=step1_dir,
        detection_url=layout_url,
        config=cfg,
        save_visualizations=debug_mode,
    )
    _step_done(
        "layout_detection", _t,
        f"pages={det_summary['total_pages']} regions={det_summary['total_regions']}",
    )
    if check_checkpoint("after_layout_detection"):
        _log("checkpoint stop after_layout_detection")
        return {"stopped": True}

    update_progress("section_split", 45)
    _t = _step_start("section_split")
    step2_dir = out_dir / "step2_section_split"
    from providers.ocr_service import ocr_region
    section_summary = split_sections(
        page_images=images,
        step1_dir=step1_dir,
        step2_dir=step2_dir,
        ocr_region=ocr_region,
        config=cfg,
        debug_mode=debug_mode,
    )
    _step_done("section_split", _t, f"sections={section_summary['num_sections']}")
    for s in section_summary["sections"]:
        _log(f"section {s['index']} pages={s['pages']} cross_page={s['is_cross_page']}")
    if check_checkpoint("after_section_split"):
        _log("checkpoint stop after_section_split")
        return {"stopped": True}

    sections = section_summary.get("sections", [])
    stitch_cfg = section_summary.get("stitch_config", {})
    if sections:
        units = []
        force_split_enabled = bool(stitch_cfg.get("force_split", False))
        for s in sections:
            section_index = s.get("index")
            section_title = s.get("title", "")
            section_strips = s.get("strips", [])
            sub_sections = s.get("sub_sections") if isinstance(s.get("sub_sections"), list) else []

            if force_split_enabled and sub_sections:
                if len(sub_sections) == 1:
                    sub = sub_sections[0]
                    units.append((
                        f"section_{section_index}",
                        sub.get("strips", section_strips),
                        section_title,
                    ))
                else:
                    for sub in sub_sections:
                        sub_index = sub.get("sub_section_index")
                        units.append((
                            f"section_{section_index}_{sub_index}",
                            sub.get("strips", section_strips),
                            section_title,
                        ))
            else:
                units.append((f"section_{section_index}", section_strips, section_title))
        unit_kind = "section"
    else:
        _log("no sections found; falling back to per-page grading")
        units = [(img.stem, None, "") for img in images]
        unit_kind = "page"

    _t = _step_start("vlm_grading")
    unit_score_dicts: list[dict[str, dict]] = []
    total = len(units)
    replies_dir = out_dir / "step3_vlm_grading"
    replies_dir.mkdir(parents=True, exist_ok=True)

    paper_meta: dict[str, Any] = {"paper_title": None, "subject": None}
    student_meta: dict[str, Any] = {"student_name": None, "class_name": None, "exam_number": None}
    header_instruction = extract_header_block(
        prompt_with_prefix,
        cfg.get("section_split", {}),
        cfg.get("_language", "en"),
    )
    if header_instruction is None:
        _log("header_extract skipped (no header block in rubric)")
    else:
        try:
            header_result = extract_header_info(
                vlm_url, images[0], instruction=header_instruction,
                max_image_pixels=max_image_pixels,
            )
            (replies_dir / "header_prompt.txt").write_text(header_instruction, encoding="utf-8")
            (replies_dir / "header_reply.txt").write_text(
                str(header_result.get("answer") or header_result.get("error") or ""),
                encoding="utf-8",
            )
            if header_result.get("ok"):
                info = parse_header_info(header_result.get("answer", ""))
                paper_meta = {"paper_title": info.get("paper_title"), "subject": info.get("subject")}
                student_meta = {
                    "student_name": info.get("student_name"),
                    "class_name": info.get("class_name"),
                    "exam_number": info.get("exam_number"),
                }
                _log(
                    f"header_extract done name={student_meta['student_name']} "
                    f"class={student_meta['class_name']} no={student_meta['exam_number']} "
                    f"title={paper_meta['paper_title']}"
                )
            else:
                _log(f"header_extract failed (degraded): {header_result.get('error')}")
        except Exception as exc:
            _log(f"header_extract error (degraded): {exc}")

    for idx, (tag, strips_or_none, title) in enumerate(units, 1):
        if strips_or_none is not None:
            raw_strips = [(int(pi), float(yt), float(yb)) for pi, yt, yb in strips_or_none]
            compress = stitch_cfg.get("compress", False)
            image_pil = None
            if compress:
                image_pil = _stitch_compressed(
                    raw_strips, step1_dir, images,
                    int(stitch_cfg.get("gap_threshold", 120)),
                    int(stitch_cfg.get("keep_margin", 50)),
                    int(stitch_cfg.get("content_pad", 20)),
                )
            if image_pil is None:
                image_pil = _stitch(raw_strips, images, stitch_cfg.get("direction", "vertical"))
            if debug_mode:
                dbg_path = step2_dir / f"{tag}.png"
                image_pil.save(dbg_path)
        else:
            image_pil = images[idx - 1]

        w = image_pil.width if hasattr(image_pil, "width") else 0
        h = image_pil.height if hasattr(image_pil, "height") else 0
        mp = (w * h) / 1_000_000
        _log(f"vlm {unit_kind} {idx}/{total} {tag} {w}x{h}px ({mp:.2f} MP)")

        prompt_for_unit = (
            slice_prompt_for_section(
                prompt_with_prefix,
                title,
                cfg.get("section_split", {}),
                cfg.get("_language", "en"),
            )
            if title else prompt_with_prefix
        )

        prompt_for_unit = append_common_output_suffix_if_missing(
            full_prompt=prompt_for_unit,
            cfg=cfg.get("section_split", {}),
            language=cfg.get("_language", "en"),
            rubrics_dir=shared_rubrics_dir,
        )

        (replies_dir / f"{tag}_prompt.txt").write_text(prompt_for_unit, encoding="utf-8")

        result = grade_page(
            vlm_url, image_pil, prompt_for_unit,
            max_tokens=max_tokens, temperature=temperature,
            max_image_pixels=max_image_pixels,
        )
        elapsed = result.get("elapsed_seconds", 0.0)

        if not result.get("ok"):
            _log(f"vlm {unit_kind} {idx} FAILED time={elapsed:.2f}s error={result.get('error')}")
            (replies_dir / f"{tag}_reply.txt").write_text(
                str(result.get("error", "")), encoding="utf-8"
            )
        else:
            answer = result.get("answer", "")
            (replies_dir / f"{tag}_reply.txt").write_text(
                f"elapsed_seconds: {elapsed:.2f}\n"
                f"finish_reason: {result.get('finish_reason')}\n"
                f"{'=' * 70}\n{answer}",
                encoding="utf-8",
            )
            unit_scores = parse_scores(answer)
            unit_score_dicts.append(unit_scores)
            _log(
                f"vlm {unit_kind} {idx} done time={elapsed:.2f}s "
                f"questions={len(unit_scores)} finish={result.get('finish_reason')}"
            )

        update_progress("vlm_grading", 50 + int(40 * idx / total))
        if check_checkpoint(f"after_{unit_kind}_{idx}"):
            _log(f"checkpoint stop after_{unit_kind}_{idx}")
            return {"stopped": True}

    scores = merge_page_scores(unit_score_dicts)
    _step_done("vlm_grading", _t, f"graded_questions={len(scores)}")

    update_progress("merge", 95)
    _t = _step_start("merge")

    result_data = build_result(scores)
    result_data["task_id"] = task_id
    result_data["paper_meta"] = paper_meta
    result_data["student_meta"] = student_meta
    result_data["input"] = {
        "paper_path": str(paper_path),
        "prompt_path": str(prompt_path),
        "student_id": student_id,
    }

    result_path = out_dir / "grading_result.json"
    result_path.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = result_data["summary"]
    _step_done(
        "merge", _t,
        f"total={summary['total_score']}/{summary['total_max']} "
        f"objective={summary['objective_score']}/{summary['objective_max']} "
        f"subjective={summary['subjective_score']}/{summary['subjective_max']}",
    )

    total_seconds = time.perf_counter() - _pipeline_start
    _log_timing_summary(total_seconds)
    result_data["processing_seconds"] = round(total_seconds, 2)
    result_path.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "stopped": False,
        "result_path": str(result_path),
        "summary": summary,
        "processing_seconds": round(total_seconds, 2),
    }
