import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from ui.services.video_processor import parse_input_to_timestamp, process_video


@patch("ui.services.video_processor.logger")
def test_parse_input_to_timestamp_string(mock_logger):
    ts, fmt = parse_input_to_timestamp("2024-07-17T12:00:00", "test")
    assert isinstance(ts, float)
    assert "IST" in fmt


def test_parse_input_to_timestamp_invalid():
    ts, fmt = parse_input_to_timestamp({"bad": "value"}, "bad")
    assert ts is None and fmt is None


@patch("ui.services.video_processor.requests.get")
@patch("ui.services.video_processor.logger")
def test_process_video_summarize_success(mock_logger, mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status": 200, "message": "sumid123"})
    res = process_video("cam1", 1721126400, 30, "Summarize")
    assert res["status"] == "success"
    assert res["summary_id"] == "sumid123"


@patch("ui.services.video_processor.requests.get")
@patch("ui.services.video_processor.logger")
def test_process_video_search_success(mock_logger, mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status": 200, "message": "embedding123"})
    res = process_video("cam1", 1721126400, 45, "Add to Search")
    assert res["status"] == "success"
    assert res["response"] == "embedding123"


@patch("ui.services.video_processor.logger")
def test_process_video_unknown_action(mock_logger):
    res = process_video("cam1", 1721126400, 20, "WrongAction")
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


@patch("ui.services.video_processor.requests.get", side_effect=Exception("API failed"))
@patch("ui.services.video_processor.logger")
def test_process_video_exception(mock_logger, mock_get):
    res = process_video("cam1", 1721126400, 30, "Summarize")
    assert res["status"] == "error"
    assert "API failed" in res["message"]
    mock_logger.error.assert_called_once()


@patch("ui.services.video_processor.logger")
def test_process_video_invalid_times(mock_logger):
    res = process_video("cam1", 1721126400, 0, "Summarize")
    assert res["status"] == "error"
    assert "End time must be after start time" in res["message"]
