import tempfile
from pathlib import Path
from unittest.mock import patch

from utils.session_paths import SessionPaths


def _patch_project(location, name):
    return patch(
        "utils.session_paths.RuntimeConfig.get_section",
        return_value={"location": location, "name": name},
    )


def test_base_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.base_dir() == Path(tmp) / "proj"


def test_session_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.session_dir("s1") == Path(tmp) / "proj" / "s1"


def test_logs_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.logs_dir("s1") == Path(tmp) / "proj" / "s1" / "logs"


def test_raw_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.raw_dir("s1") == Path(tmp) / "proj" / "s1" / "raw"


def test_result_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.result_dir("s1") == Path(tmp) / "proj" / "s1" / "result"


def test_app_log_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.app_log_path("s1") == Path(tmp) / "proj" / "s1" / "logs" / "app.log"


def test_stage_events_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.stage_events_path("s1") == (
            Path(tmp) / "proj" / "s1" / "logs" / "stage_events.jsonl"
        )


def test_metrics_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.metrics_path("s1") == (
            Path(tmp) / "proj" / "s1" / "logs" / "performance_metrics.csv"
        )


def test_utilization_logs_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.utilization_logs_dir("s1") == (
            Path(tmp) / "proj" / "s1" / "logs" / "utilization_logs"
        )


def test_transcript_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.transcript_path("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "transcription.txt"
        )


def test_teacher_transcript_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.teacher_transcript_path("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "teacher_transcription.txt"
        )


def test_segmentation_transcript_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.segmentation_transcript_path("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "content_segmentation_transcription.txt"
        )


def test_ocr_result_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.ocr_result_path("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "ocr_result.txt"
        )


def test_asr_events_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.asr_events_path("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "asr_events.jsonl"
        )


def test_va_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.va_dir("s1") == Path(tmp) / "proj" / "s1" / "raw" / "va"


def test_va_logs_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.va_logs_dir("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "va" / "logs"
        )


def test_class_statistics_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.class_statistics_path("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "va" / "class_statistics.json"
        )


def test_board_ocr_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.board_ocr_dir("s1") == (
            Path(tmp) / "proj" / "s1" / "raw" / "board_ocr"
        )


def test_summary_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.summary_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "summary.md"
        )


def test_mindmap_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.mindmap_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "mindmap.mmd"
        )


def test_topics_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.topics_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "topics.json"
        )


def test_report_md_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.report_md_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "class_report.md"
        )


def test_report_docx_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.report_docx_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "class_report.docx"
        )


def test_report_pdf_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.report_pdf_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "class_report.pdf"
        )


def test_report_fields_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.report_fields_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "class_report_fields.json"
        )


def test_mindmap_png_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.mindmap_png_path("s1") == (
            Path(tmp) / "proj" / "s1" / "result" / "mindmap_report.png"
        )


def test_returns_path_objects():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert isinstance(SessionPaths.session_dir("s1"), Path)
