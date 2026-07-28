from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from services.detection_client import (
    check_service_health,
    detect_page_layout,
    draw_detection_boxes,
    merge_overlapping_boxes,
)


def run_layout_detection(
    page_images: list[Path],
    step1_dir: Path,
    detection_url: str,
    config: dict[str, Any],
    save_visualizations: bool = False,
) -> dict[str, Any]:
    """Detect layout on each page PNG and persist results to step1_dir.

    Raises RuntimeError if the detection service is unhealthy.
    Returns a summary dict {total_pages, total_regions, pages: {...}}.
    """
    det_cfg = config.get("detection_service", {})
    if not isinstance(det_cfg, dict):
        det_cfg = {}

    target_labels = det_cfg.get("target_labels") or ["text", "table", "title"]
    min_score = float(det_cfg.get("min_score", 0.5))
    sort_boxes = bool(det_cfg.get("sort_boxes", True))
    expand_margin = int(det_cfg.get("expand_margin", 0))
    merge_enabled = bool(det_cfg.get("merge_overlapping", False))
    iou_threshold = float(det_cfg.get("iou_threshold", 0.7))
    save_vis = bool(det_cfg.get("save_visualizations", save_visualizations))

    if not check_service_health(detection_url):
        raise RuntimeError(f"layout detection service unhealthy: {detection_url}")

    step1_dir.mkdir(parents=True, exist_ok=True)

    import json

    all_detections: dict[int, list[dict[str, Any]]] = {}
    for page_path in page_images:
        # page_N.png -> N
        try:
            page_num = int(page_path.stem.split("_")[-1])
        except ValueError:
            page_num = len(all_detections) + 1

        image = Image.open(page_path).convert("RGB")
        boxes = detect_page_layout(
            page_image=image,
            service_url=detection_url,
            target_labels=target_labels,
            min_score=min_score,
            sort=sort_boxes,
            expand_margin=expand_margin,
        )
        if merge_enabled and boxes:
            boxes = merge_overlapping_boxes(boxes, iou_threshold=iou_threshold)

        all_detections[page_num] = boxes

        (step1_dir / f"page_{page_num}_detections.json").write_text(
            json.dumps(
                {"page_num": page_num, "total_regions": len(boxes), "boxes": boxes},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )

        if save_vis and boxes:
            draw_detection_boxes(
                image=image, boxes=boxes,
                output_path=step1_dir / f"page_{page_num}_detections.jpg",
            )

    summary = {
        "total_pages": len(page_images),
        "total_regions": sum(len(v) for v in all_detections.values()),
        "pages": {
            str(pn): {
                "num_regions": len(bx),
                "json_path": str(step1_dir / f"page_{pn}_detections.json"),
            }
            for pn, bx in all_detections.items()
        },
    }
    (step1_dir / "detection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
