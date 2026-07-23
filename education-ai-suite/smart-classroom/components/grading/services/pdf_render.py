"""PDF rendering for VLM grading: render each page to a PNG on disk.

Pure functions, no logging side effects — the caller (pipeline) decides how to
report progress. Uses PyMuPDF (fitz), the same engine as the legacy pipeline.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


def render_pdf_to_pngs(
    pdf_path: Path,
    out_dir: Path,
    dpi: int = 300,
    contrast_enhance: bool = False,
    contrast_factor: float = 1.5,
) -> list[Path]:
    """Render each page of ``pdf_path`` to ``out_dir/page_N.png``.

    Returns the list of written PNG paths in page order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    paths: list[Path] = []
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(matrix=matrix)
            page_path = out_dir / f"page_{i + 1}.png"
            if contrast_enhance:
                from PIL import Image, ImageEnhance
                import io
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                img = ImageEnhance.Contrast(img).enhance(contrast_factor)
                img.save(str(page_path))
            else:
                pix.save(str(page_path))
            paths.append(page_path)
    finally:
        doc.close()
    return paths


def image_info(path: Path) -> dict[str, Any]:
    """Return {width, height, megapixels, file_kb} for a page image.

    width/height are 0 if the image cannot be opened (e.g. Pillow missing);
    file size is always available from the filesystem.
    """
    size_bytes = path.stat().st_size
    width = height = 0
    try:
        from PIL import Image

        with Image.open(path) as im:
            width, height = im.size
    except Exception:
        pass
    return {
        "width": width,
        "height": height,
        "megapixels": (width * height) / 1_000_000,
        "file_kb": size_bytes / 1024,
    }
