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


def test_va_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.va_dir("s1") == Path(tmp) / "proj" / "s1" / "va"


def test_transcript_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.transcript_path("s1") == Path(tmp) / "proj" / "s1" / "transcription.txt"


def test_segmentation_transcript_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.segmentation_transcript_path("s1") == (
            Path(tmp) / "proj" / "s1" / "content_segmentation_transcription.txt"
        )


def test_summary_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.summary_path("s1") == Path(tmp) / "proj" / "s1" / "summary.md"


def test_mindmap_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.mindmap_path("s1") == Path(tmp) / "proj" / "s1" / "mindmap.mmd"


def test_topics_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.topics_path("s1") == Path(tmp) / "proj" / "s1" / "topics.json"


def test_logs_dir():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.logs_dir("s1") == Path(tmp) / "proj" / "s1" / "logs"


def test_app_log_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.app_log_path("s1") == Path(tmp) / "proj" / "s1" / "logs" / "app.log"


def test_stage_events_path():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert SessionPaths.stage_events_path("s1") == (
            Path(tmp) / "proj" / "s1" / "logs" / "stage_events.jsonl"
        )


def test_returns_path_objects():
    with tempfile.TemporaryDirectory() as tmp, _patch_project(tmp, "proj"):
        assert isinstance(SessionPaths.session_dir("s1"), Path)
