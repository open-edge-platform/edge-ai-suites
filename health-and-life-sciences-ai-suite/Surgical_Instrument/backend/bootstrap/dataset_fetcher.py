"""Prepare the CVC-ColonDB training dataset from a user-supplied raw drop.

The customer downloads CVC-ColonDB directly from the CVC lab
(http://mv.cvc.uab.es/projects/colon-qa/cvccolondb, research-use license),
accepts their terms, and drops the archive or extracted folder into
``dataset.raw_dir``. This module then:

1. If ``raw_dir`` contains a single archive (``.zip`` / ``.tar`` / ``.tar.gz`` /
   ``.tgz``), extracts it in-place.
2. Auto-detects the images + masks sub-directories under ``raw_dir`` (CVC
   distributions vary — ``images``/``masks``, ``original``/``mask``, etc.).
3. Converts each binary mask to YOLO bounding boxes via OpenCV
   ``connectedComponentsWithStats`` — same well-known technique used by
   published converters, reimplemented here so we own the code.
4. Deterministically splits the paired samples into train/val/test.
5. Writes a Linux-clean ``data.yaml`` under ``output_dir``.

Cache-hit: if ``output_dir/data.yaml`` already exists on a subsequent run,
we skip all of the above and return it directly.

We never redistribute CVC data — the archive must come from the user.
"""
from __future__ import annotations

import random
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Callable, Iterable

import cv2
import yaml

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
_MASK_EXTS = (".png", ".tif", ".tiff", ".bmp")
_ARCHIVE_EXTS = (".zip", ".tar", ".tar.gz", ".tgz")
_IMAGE_DIR_HINTS = ("images", "image", "img", "original", "originals", "frames")
_MASK_DIR_HINTS = ("masks", "mask", "gt", "groundtruth", "ground_truth", "labels_gt")


class DatasetError(RuntimeError):
    pass


def ensure_dataset(
    cfg: dict,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Return an absolute path to a ready-to-train ``data.yaml``.

    Raises :class:`DatasetError` with a customer-actionable message when the
    user hasn't dropped the CVC archive yet.
    """
    output_dir = Path(cfg["output_dir"]).resolve()
    data_yaml = output_dir / "data.yaml"

    if data_yaml.exists():
        if progress:
            progress(f"dataset: cache hit -> {data_yaml}")
        return data_yaml

    raw_dir = Path(cfg["raw_dir"]).resolve()
    if not raw_dir.exists() or not any(raw_dir.iterdir()):
        raise DatasetError(_missing_raw_message(raw_dir, cfg.get("name", "dataset")))

    _extract_any_archive(raw_dir, progress)
    images_src, masks_src = _autodetect_layout(raw_dir)
    if progress:
        progress(f"dataset: detected images={images_src} masks={masks_src}")

    conv = cfg.get("convert") or {}
    class_id = int(conv.get("class_id", 0))
    min_area_px = int(conv.get("min_area_px", 10))
    train_pct = float(conv.get("train_pct", 0.70))
    val_pct = float(conv.get("val_pct", 0.15))
    test_pct = float(conv.get("test_pct", 0.15))
    seed = int(conv.get("split_seed", 42))

    if abs(train_pct + val_pct + test_pct - 1.0) > 1e-6:
        raise DatasetError(
            f"dataset.convert splits must sum to 1.0 (got "
            f"train={train_pct} val={val_pct} test={test_pct})"
        )

    # Build the pre-split labels flat, then split into train/val/test.
    scratch_labels = output_dir / "_scratch_labels"
    scratch_labels.mkdir(parents=True, exist_ok=True)
    paired = _convert_masks_to_yolo(
        images_src, masks_src, scratch_labels, class_id, min_area_px, progress
    )
    if not paired:
        raise DatasetError(
            f"dataset: converted zero samples from {raw_dir}. Check that image "
            f"stems match mask stems (e.g. 100.png <-> 100.png)."
        )

    _split_and_write(
        paired,
        images_src,
        scratch_labels,
        output_dir,
        train_pct,
        val_pct,
        test_pct,
        seed,
        progress,
    )
    shutil.rmtree(scratch_labels, ignore_errors=True)

    _write_data_yaml(output_dir, cfg.get("class_names", ["Polyp"]), progress)
    return data_yaml


def dataset_stats(data_yaml: Path) -> dict:
    """Return a small dict describing the dataset (image counts per split)."""
    doc = yaml.safe_load(Path(data_yaml).read_text()) or {}
    root = Path(doc.get("path", data_yaml.parent))
    stats: dict = {"root": str(root), "splits": {}}
    for split_key in ("train", "val", "test"):
        rel = doc.get(split_key)
        if not rel:
            continue
        split_dir = root / rel
        if split_dir.exists():
            n = sum(1 for p in split_dir.iterdir() if p.is_file())
        else:
            n = -1
        stats["splits"][split_key] = {"path": str(split_dir), "files": n}
    stats["nc"] = doc.get("nc")
    stats["names"] = doc.get("names")
    return stats


def clear_dataset(output_dir: Path) -> None:
    """Nuke the converted dataset cache (raw_dir is left alone)."""
    if Path(output_dir).exists():
        shutil.rmtree(output_dir)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _missing_raw_message(raw_dir: Path, name: str) -> str:
    return (
        f"\n{name} raw data not found at {raw_dir}\n"
        "\n"
        "This product does not redistribute the CVC-ColonDB dataset. Please:\n"
        "  1) Visit https://pages.cvc.uab.es/CVC-Colon/index.php/databases/\n"
        "  2) Download CVC-ColonDB from http://mv.cvc.uab.es/projects/colon-qa/cvccolondb\n"
        "     (accept the CVC research-use license on their site)\n"
        f"  3) Place the .zip / .tar.gz archive (or the extracted folder) inside:\n"
        f"       {raw_dir}\n"
        "  4) Re-run `make backend-bootstrap`.\n"
        "\n"
        "Citation required in any downstream use:\n"
        "  Bernal, Sánchez, Vilariño (2012). Towards automatic polyp detection\n"
        "  with a polyp appearance model. Pattern Recognition 45(9), 3166-3182.\n"
    )


def _extract_any_archive(
    raw_dir: Path, progress: Callable[[str], None] | None
) -> None:
    """Extract every top-level archive inside ``raw_dir`` in place."""
    archives = [
        p
        for p in raw_dir.iterdir()
        if p.is_file() and any(p.name.lower().endswith(ext) for ext in _ARCHIVE_EXTS)
    ]
    for arc in archives:
        if progress:
            progress(f"dataset: extracting {arc.name}")
        name_lower = arc.name.lower()
        if name_lower.endswith(".zip"):
            with zipfile.ZipFile(arc) as zf:
                zf.extractall(raw_dir)
        elif name_lower.endswith((".tar", ".tar.gz", ".tgz")):
            mode = "r:gz" if name_lower.endswith((".gz", ".tgz")) else "r:"
            with tarfile.open(arc, mode) as tf:
                _safe_tar_extract(tf, raw_dir)
        else:  # pragma: no cover — filter above already excludes others
            continue


def _safe_tar_extract(tf: tarfile.TarFile, dst: Path) -> None:
    """Prevent path-traversal (CVE-2007-4559)."""
    dst = dst.resolve()
    for member in tf.getmembers():
        target = (dst / member.name).resolve()
        if not str(target).startswith(str(dst)):
            raise DatasetError(f"unsafe tar entry outside target dir: {member.name}")
    tf.extractall(dst)


def _autodetect_layout(raw_dir: Path) -> tuple[Path, Path]:
    """Find the images/ and masks/ directories under ``raw_dir``."""
    images_hits = list(_find_dirs(raw_dir, _IMAGE_DIR_HINTS))
    masks_hits = list(_find_dirs(raw_dir, _MASK_DIR_HINTS))

    # Filter each pair down to dirs that actually contain matching-extension files.
    images_hits = [d for d in images_hits if _has_files_with_exts(d, _IMAGE_EXTS)]
    masks_hits = [d for d in masks_hits if _has_files_with_exts(d, _MASK_EXTS)]

    # Prefer siblings that share a parent (typical CVC layout).
    for img in images_hits:
        for msk in masks_hits:
            if img.parent == msk.parent and img != msk:
                return img, msk

    if images_hits and masks_hits:
        return images_hits[0], masks_hits[0]

    raise DatasetError(
        f"dataset: could not locate paired images/masks folders under {raw_dir}. "
        f"Looked for image dirs {_IMAGE_DIR_HINTS} and mask dirs {_MASK_DIR_HINTS}."
    )


def _find_dirs(root: Path, name_hints: Iterable[str]) -> Iterable[Path]:
    lowered = {h.lower() for h in name_hints}
    for d in root.rglob("*"):
        if d.is_dir() and d.name.lower() in lowered:
            yield d


def _has_files_with_exts(d: Path, exts: tuple[str, ...]) -> bool:
    for p in d.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            return True
    return False


def _collect_stems(directory: Path, exts: tuple[str, ...]) -> dict[str, Path]:
    """Return {stem: path} for files in ``directory`` matching ``exts``."""
    out: dict[str, Path] = {}
    for p in directory.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            out.setdefault(p.stem, p)
    return out


def _convert_masks_to_yolo(
    images_dir: Path,
    masks_dir: Path,
    labels_dir: Path,
    class_id: int,
    min_area_px: int,
    progress: Callable[[str], None] | None,
) -> list[tuple[str, Path, Path, Path]]:
    """Convert each mask to YOLO bboxes; returns list of paired quadruples."""
    img_by_stem = _collect_stems(images_dir, _IMAGE_EXTS)
    mask_by_stem = _collect_stems(masks_dir, _MASK_EXTS)

    common = sorted(set(img_by_stem) & set(mask_by_stem))
    if progress:
        progress(
            f"dataset: found {len(img_by_stem)} images, {len(mask_by_stem)} masks, "
            f"{len(common)} paired"
        )

    paired: list[tuple[str, Path, Path, Path]] = []
    for stem in common:
        img_path = img_by_stem[stem]
        mask_path = mask_by_stem[stem]

        probe = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
        if probe is None:
            continue
        img_h, img_w = probe.shape[:2]

        lines = _mask_to_yolo_lines(mask_path, img_w, img_h, class_id, min_area_px)
        label_path = labels_dir / f"{stem}.txt"
        label_path.write_text("\n".join(lines))
        paired.append((stem, img_path, mask_path, label_path))

    return paired


def _mask_to_yolo_lines(
    mask_path: Path, img_w: int, img_h: int, class_id: int, min_area_px: int
) -> list[str]:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return []
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    out: list[str] = []
    for lbl in range(1, num_labels):
        x = stats[lbl, cv2.CC_STAT_LEFT]
        y = stats[lbl, cv2.CC_STAT_TOP]
        w = stats[lbl, cv2.CC_STAT_WIDTH]
        h = stats[lbl, cv2.CC_STAT_HEIGHT]
        area = stats[lbl, cv2.CC_STAT_AREA]
        if area < min_area_px:
            continue
        xc = (x + w / 2) / img_w
        yc = (y + h / 2) / img_h
        wn = w / img_w
        hn = h / img_h
        out.append(f"{class_id} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}")
    return out


def _split_and_write(
    paired: list[tuple[str, Path, Path, Path]],
    images_src: Path,  # noqa: ARG001 — kept for future symlink-mode
    scratch_labels: Path,  # noqa: ARG001
    output_dir: Path,
    train_pct: float,
    val_pct: float,
    _test_pct: float,
    seed: int,
    progress: Callable[[str], None] | None,
) -> None:
    """Copy paired files into output_dir/{images,labels}/{train,val,test}/."""
    stems = [t[0] for t in paired]
    random.Random(seed).shuffle(stems)
    stem_to_paths = {t[0]: (t[1], t[3]) for t in paired}

    n = len(stems)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)
    splits = {
        "train": stems[:n_train],
        "val": stems[n_train : n_train + n_val],
        "test": stems[n_train + n_val :],
    }
    if progress:
        progress(
            f"dataset: split -> train={len(splits['train'])} "
            f"val={len(splits['val'])} test={len(splits['test'])}"
        )

    for split, split_stems in splits.items():
        img_out = output_dir / "images" / split
        lbl_out = output_dir / "labels" / split
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for stem in split_stems:
            src_img, src_lbl = stem_to_paths[stem]
            shutil.copy2(src_img, img_out / src_img.name)
            shutil.copy2(src_lbl, lbl_out / f"{stem}.txt")


def _write_data_yaml(
    output_dir: Path,
    class_names: list[str],
    progress: Callable[[str], None] | None,
) -> None:
    doc = {
        "path": str(output_dir),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(class_names),
        "names": list(class_names),
    }
    (output_dir / "data.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    if progress:
        progress(f"dataset: wrote {output_dir / 'data.yaml'}")
