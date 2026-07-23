"""Split a paper into sections using step1 layout detection + OCR of headings.

A "section" is a contiguous region between two section headings (e.g. the whole
choice-question area, the fill-in area, the essay area). Headings are found by
OCR-ing the paragraph_title regions and matching configurable patterns (all
patterns live in config.yaml — no hardcoded text here). A section may span
multiple pages; its per-page vertical strips are stitched into one tall image.

Pure logic + image IO; the OCR function is injected so this stays testable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from PIL import Image

OcrRegionFn = Callable[[Any, list], str]  # (page_image_path, bbox) -> text


def _load_page_boxes(step1_dir: Path, page_num: int) -> list[dict]:
    jf = step1_dir / f"page_{page_num}_detections.json"
    if not jf.exists():
        return []
    data = json.loads(jf.read_text(encoding="utf-8"))
    return data.get("boxes", [])


def _find_section_starts(
    page_images: list[Path],
    step1_dir: Path,
    ocr_region: OcrRegionFn,
    title_labels: list[str],
    patterns: list[re.Pattern],
    ocr_records: list[dict] | None = None,
    debug_dir: Path | None = None,
) -> list[dict]:
    """Return section starts [{page_index, page_num, y, title, bbox}] in order.

    page_index is the 0-based index into page_images; page_num is parsed from
    the detection filename (1-based).
    If ocr_records is a list, every title-candidate box and its OCR result are
    appended to it (for debug output).
    If debug_dir is set, each candidate crop is saved there as a PNG alongside
    a sidecar .txt with the OCR result and match status.
    """
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)

    starts: list[dict] = []
    crop_index = 0
    for idx, png in enumerate(page_images):
        try:
            page_num = int(png.stem.split("_")[-1])
        except ValueError:
            page_num = idx + 1
        for box in _load_page_boxes(step1_dir, page_num):
            if box.get("label") not in title_labels:
                continue
            bbox = box.get("coordinate")
            if not bbox:
                continue
            text = (ocr_region(png, bbox) or "").strip()
            matched = any(p.match(text) for p in patterns)

            if debug_dir is not None:
                crop_index += 1
                try:
                    x0, y0, x1, y1 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                    crop = Image.open(png).convert("RGB").crop((x0, y0, x1, y1))
                    slug = f"p{page_num}_{crop_index:02d}_{'match' if matched else 'nomatch'}"
                    crop.save(debug_dir / f"{slug}.png")
                    (debug_dir / f"{slug}.txt").write_text(
                        f"page: {page_num}\nlabel: {box.get('label')}\nbbox: {bbox}\n"
                        f"matched: {matched}\nocr_text:\n{text}\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass

            if ocr_records is not None:
                ocr_records.append({
                    "page_num": page_num,
                    "label": box.get("label"),
                    "bbox": bbox,
                    "ocr_text": text,
                    "matched": matched,
                })
            if matched:
                starts.append({
                    "page_index": idx,
                    "page_num": page_num,
                    "y": float(bbox[1]),
                    "title": text,
                    "bbox": bbox,
                })
    # order by (page_index, y) — reading order across the whole paper
    starts.sort(key=lambda s: (s["page_index"], s["y"]))
    return starts


def _section_page_strips(
    start: dict,
    next_start: dict | None,
    page_images: list[Path],
) -> list[tuple[int, float, float]]:
    """Vertical strips [(page_index, y_top, y_bottom), ...] covered by a section.

    - start page: from the heading's y to bottom of page
    - middle pages: full page
    - end page (where the next heading is): top of page to next heading's y
    If the section has no next heading, it runs to the end of the last page.
    """
    strips: list[tuple[int, float, float]] = []
    start_pi = start["page_index"]
    end_pi = next_start["page_index"] if next_start else len(page_images) - 1

    for pi in range(start_pi, end_pi + 1):
        with Image.open(page_images[pi]) as im:
            _, h = im.size
        y_top = start["y"] if pi == start_pi else 0.0
        y_bottom = next_start["y"] if (next_start and pi == end_pi) else float(h)
        if y_bottom > y_top:
            strips.append((pi, y_top, y_bottom))
    return strips


def _stitch(strips: list[tuple[int, float, float]], page_images: list[Path],
            direction: str = "vertical") -> Image.Image:
    """Crop each strip and stitch into one image (vertical by default)."""
    crops: list[Image.Image] = []
    for pi, y_top, y_bottom in strips:
        with Image.open(page_images[pi]) as im:
            im = im.convert("RGB")
            w, _ = im.size
            crops.append(im.crop((0, int(y_top), w, int(y_bottom))))
    if len(crops) == 1:
        return crops[0]
    if direction == "horizontal":
        total_w = sum(c.width for c in crops)
        max_h = max(c.height for c in crops)
        out = Image.new("RGB", (total_w, max_h), (255, 255, 255))
        x = 0
        for c in crops:
            out.paste(c, (x, 0)); x += c.width
        return out
    # vertical
    max_w = max(c.width for c in crops)
    total_h = sum(c.height for c in crops)
    out = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    y = 0
    for c in crops:
        out.paste(c, (0, y)); y += c.height
    return out


def _collect_content_blocks(
    strips: list[tuple[int, float, float]],
    step1_dir: Path,
    page_images: list[Path],
) -> list[tuple[int, float, float]]:
    """Content boxes intersected with the section strips, as (page_index, y1, y2).

    Only boxes overlapping a strip's [y_top, y_bottom) are kept, clipped to it.
    Returned in reading order (strip order, then y).
    """
    blocks: list[tuple[int, float, float]] = []
    for pi, y_top, y_bottom in strips:
        try:
            page_num = int(page_images[pi].stem.split("_")[-1])
        except ValueError:
            page_num = pi + 1
        page_blocks = []
        for box in _load_page_boxes(step1_dir, page_num):
            bbox = box.get("coordinate")
            if not bbox:
                continue
            by1, by2 = float(bbox[1]), float(bbox[3])
            # clip to the strip
            cy1, cy2 = max(by1, y_top), min(by2, y_bottom)
            if cy2 > cy1:
                page_blocks.append((cy1, cy2))
        page_blocks.sort()
        for cy1, cy2 in page_blocks:
            blocks.append((pi, cy1, cy2))
    return blocks


def _merge_intervals_per_page(
    blocks: list[tuple[int, float, float]],
    gap_threshold: int,
    content_pad: int,
) -> list[tuple[int, float, float]]:
    """Merge content boxes into non-overlapping intervals, per page.

    Boxes on the same page whose gap is <= gap_threshold are joined into one
    continuous interval (so dense/overlapping regions stay intact and are copied
    verbatim). Each interval is padded by content_pad. Returns
    [(page_index, y_top, y_bottom), ...] in reading order.
    """
    # group by page, preserving page order of first appearance
    per_page: dict[int, list[tuple[float, float]]] = {}
    order: list[int] = []
    for pi, y1, y2 in blocks:
        if pi not in per_page:
            per_page[pi] = []
            order.append(pi)
        per_page[pi].append((y1, y2))

    merged: list[tuple[int, float, float]] = []
    for pi in order:
        ivs = sorted(per_page[pi])
        cur_top, cur_bot = ivs[0]
        for y1, y2 in ivs[1:]:
            if y1 - cur_bot <= gap_threshold:
                cur_bot = max(cur_bot, y2)          # join (overlap or small gap)
            else:
                merged.append((pi, cur_top, cur_bot))
                cur_top, cur_bot = y1, y2
        merged.append((pi, cur_top, cur_bot))
    # apply padding
    return [(pi, y1 - content_pad, y2 + content_pad) for pi, y1, y2 in merged]


def _stitch_compressed(
    strips: list[tuple[int, float, float]],
    step1_dir: Path,
    page_images: list[Path],
    gap_threshold: int,
    keep_margin: int,
    content_pad: int,
) -> Image.Image | None:
    """Stitch a section keeping content intact, collapsing only large gaps.

    Content boxes are first merged into non-overlapping intervals (dense regions
    become one block and are copied verbatim). Consecutive intervals are then
    joined with a small keep_margin instead of the original whitespace. Returns
    None if no content boxes are found (caller falls back to plain stitch).
    """
    blocks = _collect_content_blocks(strips, step1_dir, page_images)
    if not blocks:
        return None

    intervals = _merge_intervals_per_page(blocks, gap_threshold, content_pad)

    opened: dict[int, Image.Image] = {}

    def _page(pi: int) -> Image.Image:
        if pi not in opened:
            opened[pi] = Image.open(page_images[pi]).convert("RGB")
        return opened[pi]

    pieces: list[Image.Image] = []
    for pi, y1, y2 in intervals:
        im = _page(pi)
        w, h = im.size
        top = max(0, int(y1))
        bot = min(h, int(y2))
        if bot > top:
            pieces.append(im.crop((0, top, w, bot)))

    if not pieces:
        return None

    max_w = max(p.width for p in pieces)
    total_h = sum(p.height for p in pieces) + keep_margin * (len(pieces) - 1)
    out = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    y = 0
    for idx, p in enumerate(pieces):
        out.paste(p, (0, y))
        y += p.height + (keep_margin if idx < len(pieces) - 1 else 0)
    return out


def split_sections(
    page_images: list[Path],
    step1_dir: Path,
    step2_dir: Path,
    ocr_region: OcrRegionFn,
    config: dict[str, Any],
    debug_mode: bool = False,
) -> dict[str, Any]:
    """Split the paper into sections and write step2 artifacts.

    Returns a summary dict {num_sections, sections: [...]}. Each section carries
    its heading text, the pages it spans, and the stitched image path.
    """
    cfg = config.get("section_split", {})
    if not isinstance(cfg, dict):
        cfg = {}
    title_labels = cfg.get("title_labels") or ["paragraph_title", "title"]
    raw_patterns = cfg.get("title_patterns") or []
    patterns = [re.compile(p) for p in raw_patterns]
    direction = cfg.get("stitch_direction", "vertical")
    compress = bool(cfg.get("compress_whitespace", False))
    gap_threshold = int(cfg.get("gap_threshold", 120))
    keep_margin = int(cfg.get("keep_margin", 50))
    content_pad = int(cfg.get("content_pad", 20))
    save_ocr_debug = debug_mode

    step2_dir.mkdir(parents=True, exist_ok=True)

    ocr_records: list[dict] | None = [] if save_ocr_debug else None
    debug_dir = step2_dir / "ocr_debug" if save_ocr_debug else None
    starts = _find_section_starts(
        page_images, step1_dir, ocr_region, title_labels, patterns, ocr_records, debug_dir,
    )

    if save_ocr_debug and ocr_records is not None:
        (step2_dir / "ocr_debug.json").write_text(
            json.dumps(ocr_records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    sections: list[dict] = []
    for i, start in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else None
        strips = _section_page_strips(start, nxt, page_images)
        if not strips:
            continue

        section_entry = {
            "index": i + 1,
            "title": start["title"],
            "pages": sorted({page_images[pi].stem for pi, _, _ in strips}),
            "page_indices": [pi for pi, _, _ in strips],
            "strips": [[pi, y_top, y_bottom] for pi, y_top, y_bottom in strips],
            "compress": compress,
            "is_cross_page": len({pi for pi, _, _ in strips}) > 1,
        }

        if debug_mode:
            img = None
            if compress:
                img = _stitch_compressed(
                    strips, step1_dir, page_images,
                    gap_threshold, keep_margin, content_pad,
                )
            if img is None:
                img = _stitch(strips, page_images, direction)
            img_path = step2_dir / f"section_{i + 1}.png"
            img.save(img_path)
            section_entry["image_path"] = str(img_path)

        sections.append(section_entry)

    summary = {
        "num_sections": len(sections),
        "sections": sections,
        "stitch_config": {
            "direction": direction,
            "compress": compress,
            "gap_threshold": gap_threshold,
            "keep_margin": keep_margin,
            "content_pad": content_pad,
        },
    }
    (step2_dir / "sections.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
