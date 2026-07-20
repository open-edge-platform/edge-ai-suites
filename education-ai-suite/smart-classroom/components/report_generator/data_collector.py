"""
Data collector for the Report Generator.

Reads session data files (statistics, summary, mindmap, transcription, etc.)
and returns their contents in a format suitable for the LLM prompt.
"""

import os
import re
import json
import logging
from typing import Optional

from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
from utils.config_loader import config

logger = logging.getLogger(__name__)


MAX_KEYWORDS = 8
MAX_DIFFICULTY_POINTS = 4


def _get_session_dir(session_id: str) -> str:
    project_config = RuntimeConfig.get_section("Project")
    return os.path.join(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
    )


class DataCollector:
    """Reads all available session data for report generation."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = _get_session_dir(session_id)
        self.raw_metrics = {}
        self.max_keywords, self.max_difficulty_points = self._load_report_limits()

    @staticmethod
    def _load_report_limits() -> tuple[int, int]:
        """Read report keyword/difficulty caps from config with safe fallbacks."""
        section = getattr(config, "report", None)
        kw = getattr(section, "max_keywords", MAX_KEYWORDS) if section else MAX_KEYWORDS
        diff = getattr(section, "max_difficulty_points", MAX_DIFFICULTY_POINTS) if section else MAX_DIFFICULTY_POINTS

        try:
            kw_i = int(kw)
        except (TypeError, ValueError):
            kw_i = MAX_KEYWORDS

        try:
            diff_i = int(diff)
        except (TypeError, ValueError):
            diff_i = MAX_DIFFICULTY_POINTS

        kw_i = kw_i if kw_i > 0 else MAX_KEYWORDS
        diff_i = diff_i if diff_i > 0 else MAX_DIFFICULTY_POINTS

        return kw_i, diff_i

    def read(self, source_name: str) -> Optional[str]:
        """Read a data source by name. Returns None if data is unavailable or empty."""
        readers = {
            "class_statistics": self._read_class_statistics,
            "class_summary": self._read_class_summary,
            "mindmap": self._read_mindmap,
            "topic_segmentation": self._read_topic_segmentation,
            "teacher_transcription": self._read_teacher_transcription,
            "content_segmentation": self._read_content_segmentation,
        }

        reader = readers.get(source_name)
        if reader is None:
            logger.warning(f"[DataCollector] Unknown data source: {source_name}")
            return None

        try:
            return reader()
        except Exception as e:
            logger.error(f"[DataCollector] Failed to read {source_name}: {e}")
            return None

    def _read_class_statistics(self) -> Optional[str]:
        self.raw_metrics["video_source_count"] = self._count_video_sources()

        stats_file = os.path.join(self.session_dir, "va", "class_statistics.json")
        if not os.path.exists(stats_file):
            return None

        content = StorageManager.read_text_file(stats_file)
        if not content:
            return None

        try:
            stats = json.loads(content)
            for key in ("student_count", "stand_count", "raise_up_count"):
                if isinstance(stats.get(key), (int, float)):
                    self.raw_metrics[key] = stats[key]
        except (ValueError, TypeError):
            logger.warning("[DataCollector] class_statistics.json is not valid JSON; "
                           "skipping structured extraction.")

        return f"Class statistics:\n{content}"

    def _count_video_sources(self) -> int:
        """Count distinct camera feeds recorded this session from VA output markers.

        Each camera pipeline writes its own results file into ``<session>/va/``
        (front camera -> front_posture.txt, back camera -> back_posture.txt,
        content/board camera -> content_results.txt). The number of those present
        equals the number of camera feeds captured. Deterministic — filled
        directly into the always-on ``video_source_count`` field, never guessed by
        the LLM. Returns 0 when no video analytics ran.
        """
        va_dir = os.path.join(self.session_dir, "va")
        markers = ("front_posture.txt", "back_posture.txt", "content_results.txt")
        return sum(1 for m in markers if os.path.exists(os.path.join(va_dir, m)))

    def _read_class_summary(self) -> Optional[str]:
        summary_path = os.path.join(self.session_dir, "summary.md")
        if not os.path.exists(summary_path):
            return None

        content = StorageManager.read_text_file(summary_path)
        if not content:
            return None

        keyword_items = self._extract_summary_items(content, ("Keywords", "关键词"))
        if keyword_items:
            keyword_items = self._normalize_items(keyword_items, self.max_keywords)
            self.raw_metrics["keywords"] = self._join_items(keyword_items)
            self.raw_metrics["keywords_count"] = len(keyword_items)
        difficulty_items = self._extract_summary_items(
            content,
            ("Key Difficulty Points", "重难点"),
        )
        if difficulty_items:
            difficulty_items = self._normalize_items(difficulty_items, self.max_difficulty_points)
            self.raw_metrics["key_difficulty"] = self._join_items(difficulty_items)
            summary = self._build_mentions_summary(difficulty_items)
            if summary:
                self.raw_metrics["difficulty_mentions_summary"] = summary

        return f"Class summary:\n{content}"

    def _build_mentions_summary(self, phrases: list) -> str:
        """Per-phrase mention counts as one ready-to-render string.

        Counts each phrase's occurrences across the teacher transcript and
        OCR-scanned files (deterministic substring count, case-insensitive), then
        joins them into a single summary the template can drop in verbatim, e.g.
        ``Kepler's laws (5 times); Newton's 2nd law (2 times)``.

        Sources: ``teacher_transcription.txt`` (what the teacher said) and
        ``ocr_result.txt`` (text scanned from slides/board). Missing files are
        skipped. Returns ``""`` if there are no phrases to count.
        """
        clean = [p.strip() for p in phrases if p and p.strip()]
        if not clean:
            return ""

        haystack_parts = []
        for fname in ("teacher_transcription.txt", "ocr_result.txt"):
            path = os.path.join(self.session_dir, fname)
            if os.path.exists(path):
                text = StorageManager.read_text_file(path)
                if text:
                    haystack_parts.append(text.lower())
        haystack = "\n".join(haystack_parts)

        from utils.config_loader import config
        is_zh = getattr(config.app, "language", "en") == "zh"
        parts = []
        positive_parts = []
        for phrase in clean:
            n = haystack.count(phrase.lower()) if haystack else 0

            if n == 0 and haystack:
                anchor_counts = [
                    haystack.count(term.lower())
                    for term in self._extract_anchor_terms(phrase)
                ]
                if anchor_counts:
                    n = max(anchor_counts)

            item = f"{phrase}（{n}次）" if is_zh else f"{phrase} ({n} times)"
            parts.append(item)
            if n > 0:
                positive_parts.append(item)

        if positive_parts:
            return "；".join(positive_parts) if is_zh else "; ".join(positive_parts)

        if is_zh:
            return "当前匹配规则下未检出稳定提及证据"
        return "No stable mention evidence detected under current matching rules"

    @staticmethod
    def _extract_summary_items(content: str, headings: tuple) -> list:
        """Return the bullet items of a ``## <heading>`` markdown section as a list.

        Matches any of the given heading spellings (e.g. EN and ZH). Stops at the
        next ``##`` heading or end of text. Bullet markers are stripped and empty /
        "None" items dropped. Returns an empty list if the section is absent/empty.
        """
        for heading in headings:
            pattern = re.compile(
                r'^\s*#{1,6}\s*' + re.escape(heading) + r'\s*$(.*?)(?=^\s*#{1,6}\s|\Z)',
                re.MULTILINE | re.DOTALL,
            )
            m = pattern.search(content)
            if not m:
                continue
            items = []
            for line in m.group(1).splitlines():
                line = line.strip().lstrip('-*•').strip()
                if line and line.lower() != "none":
                    items.append(line)
            return items
        return []

    @staticmethod
    def _normalize_items(items: list, limit: int) -> list:
        """Trim, de-duplicate while preserving order, and cap item count."""
        seen = set()
        out = []
        for item in items:
            text = (item or "").strip().strip(";；,，")
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _extract_anchor_terms(phrase: str) -> list:
        """Extract a few robust anchor terms for fuzzy mention evidence.

        For CJK text: keep 2+ char chunks.
        For Latin text: keep informative words and short bi-grams.
        """
        text = (phrase or "").strip()
        if not text:
            return []

        if re.search(r"[\u4e00-\u9fff]", text):
            tokens = [
                t.strip()
                for t in re.split(r"[，,；;。\s()（）]+", text)
                if t and len(t.strip()) >= 2
            ]
            return tokens[:4]

        words = re.findall(r"[A-Za-z][A-Za-z\-']+", text)
        stop = {
            "the", "and", "for", "with", "from", "that", "this", "into",
            "between", "through", "understanding", "applying", "demonstrating",
            "connecting", "classroom", "activities", "real", "life"
        }
        words = [w for w in words if len(w) >= 4 and w.lower() not in stop]
        anchors = []
        anchors.extend(words[:3])
        if len(words) >= 2:
            anchors.append(f"{words[0]} {words[1]}")
        return anchors[:4]

    @staticmethod
    def _join_items(items: list) -> str:
        """Join extracted items with a language-appropriate separator (Chinese list
        separator when the app language is Chinese, comma+space otherwise)."""
        from utils.config_loader import config
        sep = "、" if getattr(config.app, "language", "en") == "zh" else ", "
        return sep.join(items)

    def _read_mindmap(self) -> Optional[str]:
        mindmap_path = os.path.join(self.session_dir, "mindmap.mmd")
        if not os.path.exists(mindmap_path):
            return None

        content = StorageManager.read_text_file(mindmap_path)
        if not content:
            return None

        return f"Mind map (node_tree JSON):\n{content}"

    def _read_topic_segmentation(self) -> Optional[str]:
        topics_path = os.path.join(self.session_dir, "topics.json")
        if not os.path.exists(topics_path):
            return None

        content = StorageManager.read_text_file(topics_path)
        if not content:
            return None

        return f"Topic segmentation:\n{content}"

    def _read_teacher_transcription(self) -> Optional[str]:
        path = os.path.join(self.session_dir, "teacher_transcription.txt")
        if not os.path.exists(path):
            return None

        content = StorageManager.read_text_file(path)
        if not content:
            return None

        lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
        total_sentences = len(lines)

        teacher_speaking_sec = 0
        total_chars = 0
        question_count = 0
        texts = []

        for line in lines:
            ts_match = re.match(r'\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]\s*(.*)', line)
            if ts_match:
                start = float(ts_match.group(1))
                end = float(ts_match.group(2))
                text = ts_match.group(3)
                teacher_speaking_sec += (end - start)
            else:
                text = line

            total_chars += len(text)
            texts.append(text)
            if text.endswith('？') or text.endswith('?'):
                question_count += 1

        teacher_speaking_min = teacher_speaking_sec / 60.0 if teacher_speaking_sec > 0 else 0

        total_duration_sec = 0
        cs_path = os.path.join(self.session_dir, "content_segmentation_transcription.txt")
        if os.path.exists(cs_path):
            cs_content = StorageManager.read_text_file(cs_path)
            if cs_content:
                cs_lines = cs_content.strip().split('\n')
                for cs_line in reversed(cs_lines):
                    match = re.match(r'\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]', cs_line.strip())
                    if match:
                        total_duration_sec = float(match.group(2))
                        break

        total_duration_min = total_duration_sec / 60.0 if total_duration_sec > 0 else 0
        speaking_speed = round(total_chars / teacher_speaking_min) if teacher_speaking_min > 0 else 0
        speaking_ratio = round(teacher_speaking_sec / total_duration_sec * 100, 1) if total_duration_sec > 0 else 0

        # Stash structured audio-derived metrics for direct (non-LLM) raw-field filling.
        self.raw_metrics.update({
            "question_count": question_count,
            "speaking_speed": speaking_speed,
            "teaching_duration_min": round(teacher_speaking_min, 1),
            "duration_min": round(total_duration_min, 1),
        })

        stats = (
            f"--- Teacher Speech Statistics ---\n"
            f"Total sentences: {total_sentences}\n"
            f"Total characters: {total_chars}\n"
            f"Question count (sentences ending with ?): {question_count}\n"
            f"Teacher speaking duration: {teacher_speaking_sec:.0f}s ({teacher_speaking_min:.1f} min)\n"
            f"Total class duration: {total_duration_sec:.0f}s ({total_duration_min:.1f} min)\n"
            f"Teacher speaking ratio: {speaking_ratio}%\n"
            f"Speaking speed: {speaking_speed} chars/min (based on teacher speaking time)\n"
            f"---\n"
        )

        sample = "\n".join(lines[:20])
        if len(lines) > 20:
            sample += f"\n... [{len(lines) - 20} more sentences]"

        return f"Teacher transcription analysis:\n{stats}\nSample:\n{sample}"

    def _read_content_segmentation(self) -> Optional[str]:
        path = os.path.join(self.session_dir, "content_segmentation_transcription.txt")
        if not os.path.exists(path):
            return None

        content = StorageManager.read_text_file(path)
        if not content:
            return None

        lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
        total_segments = len(lines)

        timestamps = []
        for line in lines:
            match = re.match(r'\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]', line)
            if match:
                timestamps.append((float(match.group(1)), float(match.group(2))))

        if timestamps:
            total_duration_sec = timestamps[-1][1] - timestamps[0][0]
            total_duration_min = total_duration_sec / 60.0

            bucket_size = 300  # 5 minutes
            max_time = timestamps[-1][1]
            buckets = {}
            for start, end in timestamps:
                bucket_idx = int(start // bucket_size)
                buckets[bucket_idx] = buckets.get(bucket_idx, 0) + 1

            density_report = []
            for i in range(int(max_time // bucket_size) + 1):
                t_start = i * bucket_size
                t_end = min((i + 1) * bucket_size, max_time)
                count = buckets.get(i, 0)
                density_report.append(
                    f"  {t_start//60:.0f}-{t_end//60:.0f}min: {count} segments"
                )

            if buckets:
                min_count = min(buckets.values())
                low_periods = [f"{k*bucket_size//60:.0f}-{(k+1)*bucket_size//60:.0f}min"
                               for k, v in buckets.items() if v == min_count]
            else:
                low_periods = []

            stats = (
                f"--- Content Segmentation Statistics ---\n"
                f"Total segments: {total_segments}\n"
                f"Total duration: {total_duration_sec:.0f}s ({total_duration_min:.1f} min)\n"
                f"Time range: {timestamps[0][0]:.1f}s - {timestamps[-1][1]:.1f}s\n"
                f"Avg segment duration: {total_duration_sec/total_segments:.1f}s\n"
                f"\nDensity per 5-min period (more segments = more active):\n"
                + "\n".join(density_report) + "\n"
                f"\nLow activity periods: {', '.join(low_periods) if low_periods else 'None detected'}\n"
                f"---\n"
            )
        else:
            stats = f"--- Content Segmentation ---\nTotal lines: {total_segments}\n(No timestamps detected)\n---\n"

        sample = "\n".join(lines[:10])
        if len(lines) > 10:
            sample += f"\n... [{len(lines) - 10} more segments]"

        return f"Content segmentation analysis:\n{stats}\nSample:\n{sample}"
