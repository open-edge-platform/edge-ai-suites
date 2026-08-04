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
    page_columns: int = 1,
    column_split_ratio: float = 0.5,
) -> list[Path]:
    """Render each page of ``pdf_path`` to ``out_dir/page_N.png``.

    When ``page_columns`` is 2, each rendered page is split vertically into a
    left and a right half (at ``column_split_ratio`` of the width) and emitted
    as two consecutive pages, so downstream reading order is left-then-right.
    Returns the list of written PNG paths in reading order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    from PIL import Image, ImageEnhance
    import io

    paths: list[Path] = []
    page_no = 0
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(matrix=matrix)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            if contrast_enhance:
                img = ImageEnhance.Contrast(img).enhance(contrast_factor)

            if page_columns == 2:
                split_x = int(img.width * column_split_ratio)
                halves = [
                    img.crop((0, 0, split_x, img.height)),
                    img.crop((split_x, 0, img.width, img.height)),
                ]
            else:
                halves = [img]

            for half in halves:
                page_no += 1
                page_path = out_dir / f"page_{page_no}.png"
                half.save(str(page_path))
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
