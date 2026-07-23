from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF, already a dependency (see pdf_render.py)
import yaml

logger = logging.getLogger("grading.dir")


@dataclass
class DirDefaults:
    poll_interval: float
    stable_checks: int
    idle_timeout: float


def load_dir_defaults(component_root: Path) -> DirDefaults:
    """Read poll_interval / stable_checks / idle_timeout defaults from the
    config.yaml watch section (kept as directory-task defaults)."""
    raw: dict[str, Any] = {}
    try:
        raw = yaml.safe_load((component_root / "config.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        logger.exception("failed to read config.yaml; using built-in dir defaults")
    watch = raw.get("watch") or {}
    return DirDefaults(
        poll_interval=float(watch.get("poll_interval", 5)),
        stable_checks=int(watch.get("stable_checks", 2)),
        idle_timeout=float(watch.get("idle_timeout", 180)),
    )


def discover_items(papers_dir: Path) -> list[dict[str, str]]:
    """Return work items under papers_dir. Two granularities are supported:

    - subfolder: papers_dir/<student>/*.pdf  -> key=<student>, kind="dir"
    - file:      papers_dir/<name>.pdf        -> key=<name>,    kind="file"

    Each item: {"key", "path" (abs pdf), "kind"}. Ordered by key.
    """
    items: list[dict[str, str]] = []
    if not papers_dir.is_dir():
        return items
    for child in sorted(papers_dir.iterdir()):
        if child.is_dir():
            pdfs = sorted(child.glob("*.pdf"))
            if pdfs:
                items.append({"key": child.name, "path": str(pdfs[0].resolve()), "kind": "dir"})
        elif child.is_file() and child.suffix.lower() == ".pdf":
            items.append({"key": child.stem, "path": str(child.resolve()), "kind": "file"})
    return items


def is_pdf_ready(pdf: Path, stable: dict[Path, tuple[int, float, int]], stable_checks: int) -> bool:
    """True once the PDF is stable (size+mtime unchanged for stable_checks polls)
    and openable by fitz. `stable` is caller-owned state carried across polls."""
    try:
        st = pdf.stat()
    except OSError:
        return False

    prev = stable.get(pdf)
    if prev and prev[0] == st.st_size and prev[1] == st.st_mtime:
        count = prev[2] + 1
    else:
        count = 1
    stable[pdf] = (st.st_size, st.st_mtime, count)
    if count < stable_checks:
        return False

    try:
        doc = fitz.open(str(pdf))
        n = len(doc)
        doc.close()
        return n >= 1
    except Exception:
        return False
