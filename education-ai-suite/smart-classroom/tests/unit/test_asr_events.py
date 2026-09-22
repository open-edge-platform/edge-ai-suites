import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from utils.asr_events import AsrEventWriter


def _patch_dir(tmp):
    return patch(
        "utils.asr_events.SessionPaths.asr_events_path",
        return_value=Path(tmp) / "raw" / "asr_events.jsonl",
    )


def test_write_creates_jsonl_with_chunk_fields():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        AsrEventWriter.write("s1", {
            "chunk_path": "chunks/c0.wav",
            "start_time": 0.0,
            "end_time": 30.0,
            "chunk_index": 0,
            "text": "hello\n",
            "segments": [{"speaker": "Teacher", "text": "hello", "start": 0.5, "end": 1.2}],
        })
        path = Path(tmp) / "raw" / "asr_events.jsonl"
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["chunk_index"] == 0
        assert event["start_time"] == 0.0
        assert event["segments"][0]["speaker"] == "Teacher"


def test_write_appends_each_chunk():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        AsrEventWriter.write("s1", {"chunk_index": 0, "text": "a"})
        AsrEventWriter.write("s1", {"chunk_index": 1, "text": "b"})
        AsrEventWriter.write("s1", {"event": "final", "teacher_speaker": "Speaker_00"})
        path = Path(tmp) / "raw" / "asr_events.jsonl"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[2])["event"] == "final"


def test_write_preserves_non_ascii():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        AsrEventWriter.write("s1", {"chunk_index": 0, "text": "同学们好"})
        path = Path(tmp) / "raw" / "asr_events.jsonl"
        assert "同学们好" in path.read_text(encoding="utf-8")


def test_write_swallows_os_error():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp), patch(
        "utils.asr_events.os.makedirs", side_effect=OSError("disk full")
    ):
        AsrEventWriter.write("s1", {"chunk_index": 0})  # no raise


def test_write_swallows_serialization_error():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        AsrEventWriter.write("s1", {"bad": object()})  # no raise
