from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from services.detection_client import check_service_health, detect_page_layout

FULL_WIDTH_RATIO = 0.7
SEARCH_BAND = (0.35, 0.65)
MIN_GUTTER_RATIO = 0.008
MIN_BOXES_PER_PAGE = 4
MIN_GUTTER_PAGE_FRACTION = 0.6
MAX_CENTER_SPREAD = 0.05


def _page_gutter(boxes: list[dict[str, Any]], width: int) -> dict[str, Any]:
    spanning = 0
    columnar = []
    for box in boxes:
        x1, _, x2, _ = box["coordinate"]
        if (x2 - x1) >= width * FULL_WIDTH_RATIO:
            spanning += 1
        else:
            columnar.append(box)

    vote: dict[str, Any] = {
        "spanning_boxes": spanning,
        "columnar_boxes": len(columnar),
        "total_boxes": len(boxes),
        "width": width,
    }

    if len(columnar) < MIN_BOXES_PER_PAGE:
        vote.update(gutter=False, center=None, gap_px=0, gap_range=None,
                    reason=f"too few columnar boxes ({len(columnar)})")
        return vote

    covered = [False] * width
    for box in columnar:
        x1, _, x2, _ = box["coordinate"]
        for x in range(max(0, int(x1)), min(width, int(x2))):
            covered[x] = True

    lo, hi = int(width * SEARCH_BAND[0]), int(width * SEARCH_BAND[1])
    best_start = best_len = 0
    run_start = None
    for x in range(lo, hi):
        if not covered[x]:
            if run_start is None:
                run_start = x
        else:
            if run_start is not None and (x - run_start) > best_len:
                best_start, best_len = run_start, x - run_start
            run_start = None
    if run_start is not None and (hi - run_start) > best_len:
        best_start, best_len = run_start, hi - run_start

    min_gap = int(width * MIN_GUTTER_RATIO)
    if best_len < max(1, min_gap):
        vote.update(gutter=False, center=None, gap_px=best_len,
                    gap_range=None,
                    reason=f"widest central gap {best_len}px < {min_gap}px")
        return vote

    center = (best_start + best_len / 2) / width
    vote.update(gutter=True, center=round(center, 4), gap_px=best_len,
                gap_range=[best_start, best_start + best_len],
                reason=f"gap {best_len}px centered at {center:.4f}")
    return vote


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _draw_vote(image: Image.Image, boxes: list[dict[str, Any]],
               vote: dict[str, Any], output_path: Path) -> None:
    from PIL import ImageDraw

    canvas = image.copy()
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = canvas.size
    line_width = max(2, int(width * 0.002))

    for box in boxes:
        x1, y1, x2, y2 = box["coordinate"]
        spanning = (x2 - x1) >= width * FULL_WIDTH_RATIO
        color = (255, 140, 0, 255) if spanning else (60, 180, 75, 255)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)

    lo, hi = int(width * SEARCH_BAND[0]), int(width * SEARCH_BAND[1])
    draw.rectangle([lo, 0, hi, height], fill=(0, 0, 255, 20))

    gap_range = vote.get("gap_range")
    if gap_range:
        draw.rectangle([gap_range[0], 0, gap_range[1], height],
                       fill=(230, 25, 75, 90))
        center_x = int(vote["center"] * width)
        draw.line([center_x, 0, center_x, height],
                  fill=(230, 25, 75, 255), width=line_width * 2)

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    canvas.save(str(output_path))


def _decide(votes: list[dict[str, Any]], fallback_columns: int,
            fallback_split_ratio: float) -> dict[str, Any]:
    usable = [v for v in votes if v["columnar_boxes"] >= MIN_BOXES_PER_PAGE]
    if not usable:
        return {
            "columns": fallback_columns,
            "split_ratio": fallback_split_ratio,
            "source": "fallback",
            "reason": "no page had enough layout boxes to judge",
        }

    with_gutter = [v for v in usable if v["gutter"]]
    fraction = len(with_gutter) / len(usable)
    if fraction < MIN_GUTTER_PAGE_FRACTION:
        return {
            "columns": 1,
            "split_ratio": fallback_split_ratio,
            "source": "inferred",
            "reason": f"only {len(with_gutter)}/{len(usable)} pages have a central gap",
        }

    centers = [v["center"] for v in with_gutter]
    spread = max(centers) - min(centers)
    if spread > MAX_CENTER_SPREAD:
        return {
            "columns": fallback_columns,
            "split_ratio": fallback_split_ratio,
            "source": "fallback",
            "reason": (f"gap positions inconsistent across pages "
                       f"(spread {spread:.4f} > {MAX_CENTER_SPREAD})"),
        }

    return {
        "columns": 2,
        "split_ratio": round(_median(centers), 4),
        "source": "inferred",
        "reason": (f"{len(with_gutter)}/{len(usable)} pages share a central gap "
                   f"(spread {spread:.4f})"),
    }


def infer_columns(
    page_images: list[Path],
    step_dir: Path,
    detection_url: str,
    config: dict[str, Any],
    fallback_columns: int,
    fallback_split_ratio: float,
    sample_pages: int = 4,
    save_visualizations: bool = False,
) -> dict[str, Any]:
    det_cfg = config.get("detection_service")
    if not isinstance(det_cfg, dict):
        det_cfg = {}
    target_labels = det_cfg.get("target_labels") or ["text", "table", "title"]
    min_score = float(det_cfg.get("min_score", 0.5))

    step_dir.mkdir(parents=True, exist_ok=True)

    if not check_service_health(detection_url):
        raise RuntimeError(f"layout detection service unhealthy: {detection_url}")

    sampled = page_images if sample_pages <= 0 else page_images[:sample_pages]
    votes: list[dict[str, Any]] = []
    for page_path in sampled:
        image = Image.open(page_path).convert("RGB")
        boxes = detect_page_layout(
            page_image=image,
            service_url=detection_url,
            target_labels=target_labels,
            min_score=min_score,
            sort=False,
            expand_margin=0,
        )
        vote = _page_gutter(boxes, image.width)
        vote["page"] = page_path.name
        votes.append(vote)
        if save_visualizations:
            _draw_vote(image, boxes, vote,
                       step_dir / f"{page_path.stem}_gutter.jpg")

    result = _decide(votes, fallback_columns, fallback_split_ratio)
    result["sampled_pages"] = len(sampled)
    result["votes"] = votes
    result["fallback"] = {
        "columns": fallback_columns,
        "split_ratio": fallback_split_ratio,
    }
    (step_dir / "column_inference.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
