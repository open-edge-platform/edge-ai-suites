import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from utils.stage_events import StageEventWriter


def _patch_dir(tmp):
    return patch(
        "utils.stage_events.SessionPaths.stage_events_path",
        return_value=Path(tmp) / "logs" / "stage_events.jsonl",
    )


def test_write_creates_jsonl_with_fields():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        StageEventWriter.write("s1", "summarize", "done", "t0", "t1", 1.5)
        path = Path(tmp) / "logs" / "stage_events.jsonl"
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["session_id"] == "s1"
        assert event["stage"] == "summarize"
        assert event["status"] == "done"
        assert event["duration_sec"] == 1.5
        assert event["error_class"] is None


def test_write_appends_second_line():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        StageEventWriter.write("s1", "transcribe", "done", "t0", "t1", 1.0)
        StageEventWriter.write("s1", "summarize", "failed", "t1", "t2", 2.0,
                               error_class="ValueError", error_detail="boom")
        path = Path(tmp) / "logs" / "stage_events.jsonl"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        second = json.loads(lines[1])
        assert second["status"] == "failed"
        assert second["error_class"] == "ValueError"


def test_write_swallows_os_error():
    # session_dir points somewhere, but makedirs raises -> must not propagate
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp), patch(
        "utils.stage_events.os.makedirs", side_effect=OSError("disk full")
    ):
        StageEventWriter.write("s1", "va", "done", "t0", "t1", 1.0)  # no raise
