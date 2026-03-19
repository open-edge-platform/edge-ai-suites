#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Build PDFs from markdown docs and README.
Generates individual PDFs for each file plus a combined PDF.
"""

import os
import sys
import re
import base64
import zlib
import requests
from pathlib import Path
import markdown
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Register fonts that cover Unicode box-drawing and arrow characters
# ---------------------------------------------------------------------------
_FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
_FONTS = {
    "DejaVuSansMono":           _FONT_DIR / "DejaVuSansMono.ttf",
    "DejaVuSansMono-Bold":      _FONT_DIR / "DejaVuSansMono-Bold.ttf",
    "DejaVuSansMono-Oblique":   _FONT_DIR / "DejaVuSansMono-Oblique.ttf",
    "DejaVuSans":               _FONT_DIR / "DejaVuSans.ttf",
    "DejaVuSans-Bold":          _FONT_DIR / "DejaVuSans-Bold.ttf",
}
for name, path in _FONTS.items():
    if path.exists():
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
CSS = """
@font-face {
    font-family: DejaVuSansMono;
    src: url("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf");
}
@font-face {
    font-family: DejaVuSansMono;
    font-weight: bold;
    src: url("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf");
}
@font-face {
    font-family: DejaVuSans;
    src: url("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf");
}
@font-face {
    font-family: DejaVuSans;
    font-weight: bold;
    src: url("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf");
}
@page {
    size: A4;
    margin: 2.2cm 2.4cm 2.2cm 2.4cm;
    @frame footer {
        -pdf-frame-content: footer;
        bottom: 1cm;
        height: 0.6cm;
    }
}
body {
    font-family: DejaVuSans, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.55;
    color: #1a1a1a;
}
h1 {
    font-size: 20pt;
    color: #1a3a5c;
    border-bottom: 2px solid #1a3a5c;
    padding-bottom: 4pt;
    margin-top: 18pt;
    margin-bottom: 8pt;
}
h2 {
    font-size: 14pt;
    color: #1a3a5c;
    border-bottom: 1px solid #c0cfe0;
    padding-bottom: 3pt;
    margin-top: 14pt;
    margin-bottom: 6pt;
}
h3 {
    font-size: 11.5pt;
    color: #2a4a70;
    margin-top: 10pt;
    margin-bottom: 4pt;
}
h4 {
    font-size: 10.5pt;
    color: #2a4a70;
    margin-top: 8pt;
    margin-bottom: 3pt;
}
p { margin: 0 0 6pt 0; }
code {
    font-family: DejaVuSansMono, "Courier New", Courier, monospace;
    font-size: 8.5pt;
    background-color: #f4f6f8;
    padding: 1px 4px;
    border-radius: 2px;
}
pre {
    background-color: #f4f6f8;
    border-left: 3px solid #1a3a5c;
    padding: 7pt 9pt;
    font-size: 8pt;
    font-family: DejaVuSansMono, "Courier New", Courier, monospace;
    line-height: 1.4;
    margin: 6pt 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
pre code {
    background: none;
    padding: 0;
    font-family: DejaVuSansMono, "Courier New", Courier, monospace;
}
blockquote {
    border-left: 3px solid #a0b8cc;
    margin: 6pt 0 6pt 8pt;
    padding: 2pt 8pt;
    color: #444;
    font-style: italic;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0;
    font-size: 9pt;
    table-layout: fixed;
    word-wrap: break-word;
}
th {
    background-color: #1a3a5c;
    color: #ffffff;
    padding: 5pt 7pt;
    text-align: left;
    word-wrap: break-word;
}
td {
    padding: 4pt 7pt;
    border-bottom: 1px solid #d8e4ee;
}
tr:nth-child(even) td { background-color: #f0f5fa; }
a { color: #1a3a5c; }
ul, ol { margin: 4pt 0 4pt 16pt; padding: 0; }
li { margin-bottom: 2pt; }
hr {
    border: none;
    border-top: 1px solid #c0cfe0;
    margin: 10pt 0;
}
.page-title {
    font-size: 24pt;
    color: #1a3a5c;
    font-weight: bold;
    margin-bottom: 4pt;
}
.page-subtitle {
    font-size: 11pt;
    color: #555;
    margin-bottom: 20pt;
}
.chapter-break { page-break-before: always; }
"""

FOOTER_HTML = """
<div id="footer" style="text-align:center; font-size:8pt; color:#888;">
    ROS2 KPI Monitoring Stack &mdash; Page <pdf:pagenumber/> of <pdf:pagecount/>
</div>
"""

MD_EXTENSIONS = ['tables', 'fenced_code', 'codehilite', 'toc', 'nl2br', 'sane_lists']

# ---------------------------------------------------------------------------
# Mermaid rendering via Kroki.io
# ---------------------------------------------------------------------------
_MERMAID_RE = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)
_mermaid_cache: dict = {}


def render_mermaid_b64(diagram: str) -> str | None:
    """Send a Mermaid diagram to Kroki.io; return base64-encoded PNG or None."""
    if diagram in _mermaid_cache:
        return _mermaid_cache[diagram]
    try:
        compressed = zlib.compress(diagram.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        url = f"https://kroki.io/mermaid/png/{encoded}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        resp.raise_for_status()
        b64 = base64.b64encode(resp.content).decode('ascii')
        _mermaid_cache[diagram] = b64
        return b64
    except Exception as e:
        print(f"    \u26a0\ufe0f  Mermaid render failed: {e}")
        return None


def preprocess_mermaid(text: str) -> str:
    """Replace ```mermaid blocks with <img> data-URI tags (PNG from Kroki.io)."""
    def replace(m: re.Match) -> str:
        diagram = m.group(1).strip()
        b64 = render_mermaid_b64(diagram)
        if b64:
            return f'\n<img src="data:image/png;base64,{b64}" style="max-width:100%; display:block; margin:8pt auto;" />\n'
        return f'\n```\n{diagram}\n```\n'
    return _MERMAID_RE.sub(replace, text)


def cleanup_tmp():
    pass  # No temp files when using data URIs

# Emoji Unicode ranges to strip (xhtml2pdf cannot render them)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # Misc symbols, emoticons, transport, etc.
    "\U00002600-\U000027BF"  # Misc symbols (✓ ✗ ★ etc)
    "\U0001FA00-\U0001FFFF"  # Extended symbols
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]",
    flags=re.UNICODE,
)


def strip_emoji(text: str) -> str:
    """Remove emoji characters that xhtml2pdf cannot render."""
    # Remove emoji; collapse any resulting double-spaces
    cleaned = _EMOJI_RE.sub('', text)
    # Clean up lines that are now just whitespace after emoji removal
    cleaned = re.sub(r'^[ \t]+$', '', cleaned, flags=re.MULTILINE)
    return cleaned


def md_to_html(md_text: str, title: str = "") -> str:
    md_text = strip_emoji(md_text)
    md_text = preprocess_mermaid(md_text)
    body = markdown.markdown(md_text, extensions=MD_EXTENSIONS)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>{CSS}</style>
</head>
<body>
{FOOTER_HTML}
{body}
</body>
</html>"""


def html_to_pdf(html: str, dest_path: Path) -> bool:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        result = pisa.CreatePDF(html.encode("utf-8"), dest=f, encoding="utf-8")
    return not result.err


def convert_file(src: Path, dest: Path):
    text = src.read_text(encoding="utf-8")
    # Plain text files (e.g. CHEATSHEET.txt) get wrapped in a code block
    if src.suffix == ".txt":
        text = "```\n" + text + "\n```"
    html = md_to_html(text, title=src.stem)
    ok = html_to_pdf(html, dest)
    status = "✅" if ok else "❌"
    print(f"  {status}  {src.name}  →  {dest.name}")
    return ok


def build_combined(sources: list[tuple[Path, str]], dest: Path):
    """Merge all source files into one PDF with chapter breaks."""
    parts = []
    for i, (src, label) in enumerate(sources):
        text = src.read_text(encoding="utf-8")
        if src.suffix == ".txt":
            text = "```\n" + text + "\n```"
        text = strip_emoji(text)
        text = preprocess_mermaid(text)
        body = markdown.markdown(text, extensions=MD_EXTENSIONS)
        break_cls = ' class="chapter-break"' if i > 0 else ''
        parts.append(f'<div{break_cls}>\n<p class="page-subtitle">{label}</p>\n{body}\n</div>')

    cover = """
<div style="text-align:center; margin-top:120pt;">
  <p class="page-title">ROS2 KPI Monitoring Stack</p>
  <p class="page-subtitle">Documentation</p>
  <hr style="width:40%; margin:20pt auto;"/>
  <p style="font-size:9pt; color:#888;">Generated documentation &mdash; all guides combined</p>
</div>
<div class="chapter-break"></div>
"""
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>{CSS}</style>
</head>
<body>
{FOOTER_HTML}
{cover}
{''.join(parts)}
</body>
</html>"""

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        result = pisa.CreatePDF(html.encode("utf-8"), dest=f, encoding="utf-8")
    ok = not result.err
    status = "✅" if ok else "❌"
    print(f"  {status}  Combined  →  {dest.name}")
    return ok


def main():
    repo = Path(__file__).parent.parent  # ros2-kpi/
    out_dir = repo / "docs" / "pdf"

    sources = [
        (repo / "README.md",                   "README"),
        (repo / "docs" / "QUICK_START.md",     "Quick Start"),
        (repo / "docs" / "COMMANDS.md",        "Command Reference"),
        (repo / "docs" / "ARCHITECTURE.md",    "Architecture"),
        (repo / "docs" / "IMPROVEMENTS.md",    "Improvements"),
        (repo / "docs" / "CHEATSHEET.txt",     "Cheat Sheet"),
    ]

    print("\n📄 Building PDFs...\n")

    ok_all = True
    for src, label in sources:
        if not src.exists():
            print(f"  ⚠️   {src.name} not found, skipping")
            continue
        dest = out_dir / (src.stem + ".pdf")
        ok_all &= convert_file(src, dest)

    print()
    combined_dest = out_dir / "ros2-kpi-docs-complete.pdf"
    existing = [(s, l) for s, l in sources if s.exists()]
    ok_all &= build_combined(existing, combined_dest)

    print(f"\n{'✅ All PDFs generated' if ok_all else '⚠️  Some PDFs failed'}.")
    print(f"📁 Output: {out_dir}\n")
    cleanup_tmp()
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
