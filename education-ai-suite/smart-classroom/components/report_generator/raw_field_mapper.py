"""Resolve report 'raw' template fields directly from structured session data.

'raw' fields (see ``field_catalog``) carry measured values — student counts,
hand-raise counts, speech rate, durations — and must NEVER be invented by the
LLM. They are filled here from the structured numbers ``DataCollector`` stashes
while reading the session (``va/class_statistics.json`` + teacher-transcription
metrics), plus session/config metadata.

Any raw field without a wired data source falls back to a neutral "no data"
marker so a filled template never shows a bare ``{placeholder}``.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# Display units for numeric raw fields, keyed by field code: (zh_unit, en_unit).
# One declarative table so unit strings live in a single place instead of being
# scattered through resolve_raw_fields. A field absent from this map renders as a
# bare value. Units stay in code (not the template) so a missing value can drop
# its unit with it — see _fmt_with_unit / resolve_raw_fields.
FIELD_UNITS = {
    "attendance": ("人", "students"),
    "hand_raise_count": ("人次", "person-times"),
    "hand_raise_avg": ("次", "times per person"),
    "question_count": ("次", "questions"),
    "speaking_speed": ("字/分", "characters/minute"),
    "teaching_duration": ("分钟", "min"),
    "duration": ("分钟", "min"),
}


def _no_data(language: str) -> str:
    return "暂无数据" if language == "zh" else "N/A"


def _fmt_with_unit(field_code: str, value, language: str) -> str | None:
    """Format ``value`` with ``field_code``'s unit, or None when there is no value.

    Returning None (rather than a unit-only string) lets the caller fall back to
    the no-data marker and keeps a lone unit from rendering without a number.
    A field absent from ``FIELD_UNITS`` is returned as a bare value.
    """
    if value is None or value == "":
        return None
    units = FIELD_UNITS.get(field_code)
    if not units:
        return str(value)
    zh_unit, en_unit = units
    unit = zh_unit if language == "zh" else en_unit
    return f"{value} {unit}"


def _manual_default_values(language: str) -> dict:
    """Default placeholders for manual basic-info fields when left blank."""
    if language == "zh":
        return {
            "school_name": "XXX中学",
            "class_name": "八（3）班",
            "course_name": "XXXX",
            "teacher_name": "XX老师",
        }
    return {
        "school_name": "XXX Middle School",
        "class_name": "Grade 8 - Class 3",
        "course_name": "XXXX",
        "teacher_name": "Teacher XX",
    }


def _session_start_time(session_id: str) -> datetime | None:
    """Best-effort parse of the session start timestamp from session id.

    Session ids are generated as YYYYMMDD-HHMMSS-xxxx.
    """
    if not session_id:
        return None
    parts = session_id.split("-")
    if len(parts) < 2:
        return None
    try:
        return datetime.strptime(f"{parts[0]}-{parts[1]}", "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _format_report_delay(session_id: str, duration_sec, language: str) -> str | None:
    """Return a human-readable delay like '8 min after class'.

    Uses session start time + measured class duration as a best-effort class-end
    timestamp.
    """
    if duration_sec is None:
        return None
    try:
        duration_value_sec = float(duration_sec)
    except (TypeError, ValueError):
        return None
    if duration_value_sec <= 0:
        return None
    start_time = _session_start_time(session_id)
    if start_time is None:
        return None

    from datetime import timedelta
    class_end = start_time + timedelta(seconds=duration_value_sec)
    delay_minutes = max(0, round((datetime.now() - class_end).total_seconds() / 60.0))
    if language == "zh":
        return f"下课后{delay_minutes}分钟"
    return f"{delay_minutes} min after class"


def _format_report_time(language: str) -> str:
    """Language-aware report timestamp string."""
    now = datetime.now()
    if language == "zh":
        return f"{now.year}年{now.month}月{now.day}日 {now.hour:02d}:{now.minute:02d}"
    return now.strftime("%Y-%m-%d %H:%M")


def _get_pacing_thresholds() -> tuple[int, int]:
    """Return (slow_max, fast_min) for pacing classification from config."""
    slow_default = 260
    fast_default = 520
    try:
        from utils.config_loader import config
        section = getattr(config, "report", None)
        slow = getattr(section, "pacing_slow_max", slow_default) if section else slow_default
        fast = getattr(section, "pacing_fast_min", fast_default) if section else fast_default
    except Exception:
        return slow_default, fast_default

    try:
        slow_i = int(slow)
    except (TypeError, ValueError):
        slow_i = slow_default

    try:
        fast_i = int(fast)
    except (TypeError, ValueError):
        fast_i = fast_default

    if slow_i <= 0:
        slow_i = slow_default
    if fast_i <= 0:
        fast_i = fast_default
    if slow_i >= fast_i:
        slow_i, fast_i = slow_default, fast_default

    return slow_i, fast_i


def _build_pacing_assessment(
    speaking_speed: int | float | None,
    teaching_duration_min: int | float | None,
    language: str,
) -> str | None:
    """Return a deterministic pacing assessment from speech-rate metrics."""
    if speaking_speed is None:
        return None

    try:
        speed = float(speaking_speed)
    except (TypeError, ValueError):
        return None

    duration = None
    if teaching_duration_min is not None:
        try:
            duration = float(teaching_duration_min)
        except (TypeError, ValueError):
            duration = None

    slow_max, fast_min = _get_pacing_thresholds()

    if language == "zh":
        if speed >= fast_min:
            base = "整体节奏偏快"
        elif speed <= slow_max:
            base = "整体节奏偏慢"
        else:
            base = "整体节奏较为适中"

        if duration is not None:
            return f"{base}（基于{int(round(speed))}字/分，讲授时长约{duration:.1f}分钟）"
        return f"{base}（基于{int(round(speed))}字/分）"

    if speed >= fast_min:
        base = "Slightly fast pace"
    elif speed <= slow_max:
        base = "Slightly slow pace"
    else:
        base = "Well-paced delivery"

    if duration is not None:
        return (
            f"{base} based on a speaking speed of {int(round(speed))} characters/minute "
            f"over a {duration:.1f}-minute teaching segment"
        )
    return f"{base} based on a speaking speed of {int(round(speed))} characters/minute"


def resolve_raw_fields(collector, raw_codes, language: str = "en") -> dict:
    """Return ``{field_code: value_str}`` for the requested raw field codes.

    ``collector`` must have already run its reads so ``collector.raw_metrics`` is
    populated. Codes with no available source get the language-appropriate no-data
    marker.
    """
    metrics = getattr(collector, "raw_metrics", {}) or {}
    nd = _no_data(language)
    session_id = getattr(collector, "session_id", "")

    # Total class duration is resolved once from a single source (audio timeline
    # for audio sessions, video length for video-only) — independent of which
    # data-source readers ran. Falls back to any duration already in metrics.
    duration_sec = None
    duration_min = None
    if hasattr(collector, "get_total_duration_sec"):
        duration_sec = collector.get_total_duration_sec()
        if isinstance(duration_sec, (int, float)) and duration_sec > 0:
            duration_min = round(float(duration_sec) / 60.0, 2)
    elif hasattr(collector, "get_total_duration_min"):
        duration_min = collector.get_total_duration_min()
        if isinstance(duration_min, (int, float)) and duration_min > 0:
            duration_sec = float(duration_min) * 60.0
        else:
            duration_min = None
    elif isinstance(metrics.get("duration_min"), (int, float)):
        duration_sec = float(metrics.get("duration_min")) * 60.0
        duration_min = float(metrics.get("duration_min"))

    if not (isinstance(duration_sec, (int, float)) and duration_sec > 0):
        duration_sec = None
    if not (isinstance(duration_min, (int, float)) and duration_min > 0):
        duration_min = None

    student_count = metrics.get("student_count")
    raise_up = metrics.get("raise_up_count")

    def unit(code, value):
        return _fmt_with_unit(code, value, language)

    speaking_speed = metrics.get("speaking_speed")
    # 0 chars/min means no usable speech signal — treat as no data, not "0 字/分".
    speaking_speed_str = unit("speaking_speed", speaking_speed) if speaking_speed else None

    hand_raise_avg = None
    if raise_up is not None and student_count:
        hand_raise_avg = round(raise_up / student_count, 1)

    resolved = {
        "attendance": unit("attendance", student_count),
        "hand_raise_count": unit("hand_raise_count", raise_up),
        "hand_raise_avg": unit("hand_raise_avg", hand_raise_avg),
        "question_count": unit("question_count", metrics.get("question_count")),
        "speaking_speed": speaking_speed_str,
        "pacing_assessment": _build_pacing_assessment(
            metrics.get("speaking_speed"),
            metrics.get("teaching_duration_min"),
            language,
        ),
        "teaching_duration": unit("teaching_duration", metrics.get("teaching_duration_min")),
        "duration": unit("duration", duration_min),
        "keywords": metrics.get("keywords"),
        "key_difficulty": metrics.get("key_difficulty"),
        "difficulty_mentions_summary": metrics.get("difficulty_mentions_summary"),
        "report_time": _format_report_time(language),
        "report_delay_after_class": _format_report_delay(
            session_id,
            duration_sec,
            language,
        ),
        "video_source_count": metrics.get("video_source_count"),
    }

    # Manual fields (school/class/course/teacher) are teacher-typed and have no
    # measured source: when selected but left blank they should render a visible
    # default placeholder so teachers know where to edit, NOT the "no data" marker.
    from components.report_generator.field_catalog import get_manual_field_codes
    manual_codes = get_manual_field_codes()
    manual_defaults = _manual_default_values(language)

    values = {}
    for code in raw_codes:
        val = resolved.get(code)
        if val is None or val == "":
            values[code] = manual_defaults.get(code, "") if code in manual_codes else nd
        else:
            values[code] = str(val)

    # Filled after the loop, not via `resolved`: an empty note must stay "" — the
    # loop's no-data fallback would turn it into "暂无数据" mid-sentence.
    if "keywords_count_note" in raw_codes:
        kw_count = metrics.get("keywords_count")
        if kw_count:
            values["keywords_count_note"] = (
                f"（共{kw_count}个）" if language == "zh" else f" ({kw_count} total)"
            )
        else:
            values["keywords_count_note"] = ""

    return values
