from __future__ import annotations

import re


class MarkdownHeadingSplitter:
    """Structure-aware markdown splitter. Splits along ATX headings (``#`` …
    ``######``) and keeps a heading-path breadcrumb per section. Provides an
    LCA-aware merge that greedily concatenates adjacent sections sharing a
    common parent heading, preventing wrong-parent metadata gluing onto the
    previous parent's tail."""

    _MIN_LCA_DEPTH = 2

    @staticmethod
    def split(text: str) -> list[tuple[str, str]]:
        """Returns ``[(heading_path, body), ...]``. Body includes the heading
        line itself so the section is self-describing. If the document has no
        headings, returns ``[("", text)]`` unchanged."""
        lines = text.split("\n")
        if not any(re.match(r"^#{1,6}\s+\S", ln) for ln in lines):
            return [("", text)]

        sections: list[tuple[str, str]] = []
        current_path: list[tuple[int, str]] = []
        current_body: list[str] = []
        current_path_str = ""

        def _flush() -> None:
            if current_body:
                body = "\n".join(current_body).strip()
                if body:
                    sections.append((current_path_str, body))

        for line in lines:
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                _flush()
                current_body.clear()
                level = len(match.group(1))
                title = match.group(2).strip()
                while current_path and current_path[-1][0] >= level:
                    current_path.pop()
                current_path.append((level, title))
                current_path_str = " > ".join(t for _, t in current_path)
                current_body.append(line)
            else:
                current_body.append(line)
        _flush()
        return sections

    @classmethod
    def merge_small(
        cls,
        sections: list[tuple[str, str]],
        target_chars: int,
    ) -> list[tuple[str, str]]:
        """Greedily concatenate adjacent sections whose combined body fits in
        ``target_chars``, but only when their heading-path LCA depth is
        ``>= _MIN_LCA_DEPTH`` (same ``## parent``)."""
        if not sections:
            return sections

        def _lca(a: str, b: str) -> tuple[str, int]:
            pa = a.split(" > ") if a else []
            pb = b.split(" > ") if b else []
            common: list[str] = []
            for x, y in zip(pa, pb):
                if x == y:
                    common.append(x)
                else:
                    break
            return " > ".join(common), len(common)

        merged: list[tuple[str, str]] = []
        for path, body in sections:
            if merged:
                prev_path, prev_body = merged[-1]
                combined_len = len(prev_body) + 1 + len(body)
                lca_path, lca_depth = _lca(prev_path, path)
                if combined_len <= target_chars and lca_depth >= cls._MIN_LCA_DEPTH:
                    merged[-1] = (lca_path, f"{prev_body}\n{body}")
                    continue
            merged.append((path, body))
        return merged
