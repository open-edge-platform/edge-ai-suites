#!/usr/bin/env python3
"""Prepare a small, leakage-free REAL-Colon YOLO dataset for fast training.

This reproduces the flow described in docs/REAL_COLON_VALIDATION_HANDOFF.md:

  * Convert REAL-Colon Pascal VOC XML boxes -> YOLO labels.
  * Cap positives per video (``--max-pos-per-video``) so training stays fast.
  * Split BY VIDEO (study), so train/val/test never share frames from the same
    procedure. This gives an honest cross-video evaluation instead of the
    frame-level random split used by backend/bootstrap/dataset_fetcher.py.

Output layout matches what training expects (Ultralytics + backend bootstrap):

    <out>/images/{train,val,test}/*.jpg
    <out>/labels/{train,val,test}/*.txt
    <out>/data.yaml

Because ``make backend-bootstrap`` cache-hits on ``<output_dir>/data.yaml``,
writing this dataset to the configured dataset output_dir (the default here)
means the next ``make backend-bootstrap`` trains on it directly — no code or
config change required.

Usage (from the surgical-instrument project root):
    .venv-backend/bin/python scripts/realcolon_prepare_yolo.py \
        --raw datasets/REAL-Colon/raw \
        --out datasets/REAL-Colon \
        --max-pos-per-video 800

Explicit video-level split (recommended for reproducible eval):
    .venv-backend/bin/python scripts/realcolon_prepare_yolo.py \
        --val-studies 002-010 --test-studies 004-008
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


def _log(msg: str) -> None:
    print(f"[realcolon] {msg}", flush=True)


def _find_study_pairs(raw_dir: Path) -> list[tuple[str, Path, Path]]:
    """Return ``(study_id, frames_dir, annotations_dir)`` for each study.

    REAL-Colon studies extract as sibling ``SSS-VVV_frames`` and
    ``SSS-VVV_annotations`` directories. Match them by common prefix.
    """
    pairs: list[tuple[str, Path, Path]] = []
    for frames_dir in sorted(raw_dir.rglob("*_frames")):
        if not frames_dir.is_dir():
            continue
        study_id = frames_dir.name[: -len("_frames")]
        ann_dir = frames_dir.with_name(study_id + "_annotations")
        if ann_dir.is_dir():
            pairs.append((study_id, frames_dir, ann_dir))
    return pairs


def _collect_images(frames_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in frames_dir.iterdir():
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
            out.setdefault(p.stem, p)
    return out


def _voc_to_yolo_lines(xml_path: Path, class_id: int) -> list[str] | None:
    """Parse a VOC XML file into YOLO lines.

    Returns a (possibly empty) list of ``class xc yc w h`` strings. An empty
    list means a valid negative (background) frame. ``None`` means the XML was
    unusable and the frame should be skipped entirely.
    """
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return None
    size = root.find("size")
    if size is None:
        return None
    try:
        img_w = float(size.findtext("width", "0") or 0)
        img_h = float(size.findtext("height", "0") or 0)
    except (TypeError, ValueError):
        return None
    if img_w <= 0 or img_h <= 0:
        return None

    lines: list[str] = []
    for obj in root.findall("object"):
        box = obj.find("bndbox")
        if box is None:
            continue
        try:
            xmin = float(box.findtext("xmin", "0") or 0)
            ymin = float(box.findtext("ymin", "0") or 0)
            xmax = float(box.findtext("xmax", "0") or 0)
            ymax = float(box.findtext("ymax", "0") or 0)
        except (TypeError, ValueError):
            continue
        if xmax <= xmin or ymax <= ymin:
            continue
        xc = (xmin + xmax) / 2.0 / img_w
        yc = (ymin + ymax) / 2.0 / img_h
        wn = (xmax - xmin) / img_w
        hn = (ymax - ymin) / img_h
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}")
    return lines


def _prepare_study_samples(
    study_id: str,
    frames_dir: Path,
    ann_dir: Path,
    class_id: int,
    max_pos: int,
    neg_per_video: int,
    rng: random.Random,
) -> list[tuple[str, Path, list[str]]]:
    """Return capped ``(stem, image_path, yolo_lines)`` samples for one study."""
    images = _collect_images(frames_dir)
    positives: list[tuple[str, Path, list[str]]] = []
    negatives: list[tuple[str, Path, list[str]]] = []

    for stem, img_path in images.items():
        xml_path = ann_dir / f"{stem}.xml"
        if not xml_path.is_file():
            continue
        lines = _voc_to_yolo_lines(xml_path, class_id)
        if lines is None:
            continue
        if lines:
            positives.append((stem, img_path, lines))
        else:
            negatives.append((stem, img_path, lines))

    rng.shuffle(positives)
    rng.shuffle(negatives)
    if max_pos > 0:
        positives = positives[:max_pos]
    if neg_per_video > 0:
        negatives = negatives[:neg_per_video]
    else:
        negatives = []

    samples = positives + negatives
    _log(
        f"{study_id}: {len(images)} frames -> "
        f"{len(positives)} positives, {len(negatives)} negatives kept"
    )
    return samples


def _assign_splits(
    study_ids: list[str],
    val_studies: set[str],
    test_studies: set[str],
    train_pct: float,
    val_pct: float,
    test_pct: float,
    rng: random.Random,
) -> tuple[dict[str, str], bool]:
    """Map each study to a split. Returns (mapping, frame_level_fallback)."""
    # Explicit override wins.
    if val_studies or test_studies:
        mapping = {}
        for sid in study_ids:
            if sid in test_studies:
                mapping[sid] = "test"
            elif sid in val_studies:
                mapping[sid] = "val"
            else:
                mapping[sid] = "train"
        return mapping, False

    n = len(study_ids)
    if n < 3:
        # Not enough distinct videos for a clean 3-way video-level split.
        return {}, True

    shuffled = list(study_ids)
    rng.shuffle(shuffled)
    n_test = max(1, round(n * test_pct))
    n_val = max(1, round(n * val_pct))
    while n_test + n_val >= n:  # guarantee >=1 training video
        if n_test > 1:
            n_test -= 1
        elif n_val > 1:
            n_val -= 1
        else:
            break
    test_ids = shuffled[:n_test]
    val_ids = shuffled[n_test : n_test + n_val]
    mapping = {}
    for sid in shuffled:
        if sid in test_ids:
            mapping[sid] = "test"
        elif sid in val_ids:
            mapping[sid] = "val"
        else:
            mapping[sid] = "train"
    return mapping, False


def _reset_out_dirs(out: Path) -> None:
    for sub in ("images", "labels"):
        for split in ("train", "val", "test"):
            d = out / sub / split
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
    stale = out / "data.yaml"
    if stale.exists():
        stale.unlink()


def _write_sample(out: Path, split: str, stem: str, img_path: Path, lines: list[str], link: bool) -> None:
    img_dst = out / "images" / split / img_path.name
    lbl_dst = out / "labels" / split / f"{stem}.txt"
    if link:
        if img_dst.exists() or img_dst.is_symlink():
            img_dst.unlink()
        img_dst.symlink_to(img_path.resolve())
    else:
        shutil.copy2(img_path, img_dst)
    lbl_dst.write_text("\n".join(lines))


def _write_data_yaml(out: Path, names: list[str], splits_present: dict[str, int]) -> None:
    lines = [
        f"path: {out.resolve()}",
        "train: images/train",
        # Ultralytics requires val; fall back to train if val ended up empty.
        f"val: images/{'val' if splits_present.get('val') else 'train'}",
    ]
    if splits_present.get("test"):
        lines.append("test: images/test")
    lines.append(f"nc: {len(names)}")
    lines.append("names: [" + ", ".join(names) + "]")
    (out / "data.yaml").write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", type=Path, default=repo_root / "datasets" / "REAL-Colon" / "raw",
                   help="Directory holding extracted SSS-VVV_frames/ + SSS-VVV_annotations/ pairs")
    p.add_argument("--out", type=Path, default=repo_root / "datasets" / "REAL-Colon",
                   help="Output dataset dir (default matches dataset.output_dir so backend-bootstrap cache-hits it)")
    p.add_argument("--max-pos-per-video", type=int, default=800,
                   help="Max positive (polyp) frames kept per video (0 = all)")
    p.add_argument("--neg-per-video", type=int, default=0,
                   help="Max negative (background) frames kept per video (0 = none)")
    p.add_argument("--class-id", type=int, default=0, help="YOLO class id for Polyp")
    p.add_argument("--names", nargs="+", default=["Polyp"], help="Class names")
    p.add_argument("--val-studies", nargs="*", default=[], help="Explicit study ids for val split")
    p.add_argument("--test-studies", nargs="*", default=[], help="Explicit study ids for test split")
    p.add_argument("--train-pct", type=float, default=0.70)
    p.add_argument("--val-pct", type=float, default=0.15)
    p.add_argument("--test-pct", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--symlink", action="store_true",
                   help="Symlink images instead of copying (saves disk, needs stable raw dir)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    raw: Path = args.raw
    out: Path = args.out

    if not raw.exists():
        _log(f"ERROR: raw dir not found: {raw}")
        return 2

    pairs = _find_study_pairs(raw)
    if not pairs:
        _log(f"ERROR: no SSS-VVV_frames/ + SSS-VVV_annotations/ pairs under {raw}")
        return 2
    _log(f"found {len(pairs)} study/video pair(s): {', '.join(p[0] for p in pairs)}")

    rng = random.Random(args.seed)

    # Convert + cap per video first (deterministic per-study RNG).
    per_study: dict[str, list[tuple[str, Path, list[str]]]] = {}
    for study_id, frames_dir, ann_dir in pairs:
        per_study[study_id] = _prepare_study_samples(
            study_id, frames_dir, ann_dir,
            args.class_id, args.max_pos_per_video, args.neg_per_video,
            random.Random(f"{args.seed}:{study_id}".__hash__() & 0xFFFFFFFF),
        )

    study_ids = list(per_study.keys())
    mapping, frame_fallback = _assign_splits(
        study_ids, set(args.val_studies), set(args.test_studies),
        args.train_pct, args.val_pct, args.test_pct, rng,
    )

    _reset_out_dirs(out)
    splits_present = {"train": 0, "val": 0, "test": 0}

    if frame_fallback:
        _log(
            f"WARNING: only {len(study_ids)} video(s) available; a clean "
            f"video-level split needs >=3. Falling back to a frame-level split "
            f"(train/val/test may share frames from the same video)."
        )
        pooled: list[tuple[str, Path, list[str]]] = []
        for samples in per_study.values():
            pooled.extend(samples)
        rng.shuffle(pooled)
        n = len(pooled)
        n_train = int(n * args.train_pct)
        n_val = int(n * args.val_pct)
        buckets = {
            "train": pooled[:n_train],
            "val": pooled[n_train : n_train + n_val],
            "test": pooled[n_train + n_val :],
        }
        for split, samples in buckets.items():
            for stem, img_path, lines in samples:
                _write_sample(out, split, stem, img_path, lines, args.symlink)
                splits_present[split] += 1
    else:
        for study_id, samples in per_study.items():
            split = mapping[study_id]
            for stem, img_path, lines in samples:
                _write_sample(out, split, stem, img_path, lines, args.symlink)
                splits_present[split] += 1
        video_split = {s: [sid for sid in study_ids if mapping[sid] == s] for s in ("train", "val", "test")}
        _log(f"video-level split -> {video_split}")

    _write_data_yaml(out, args.names, splits_present)
    _log(
        f"wrote {out / 'data.yaml'} | "
        f"train={splits_present['train']} val={splits_present['val']} test={splits_present['test']}"
    )
    _log("done. Next: make backend-bootstrap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
