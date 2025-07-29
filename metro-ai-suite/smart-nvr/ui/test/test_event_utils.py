import pytest
from unittest.mock import patch, MagicMock
from ui.services.event_utils import format_timestamp, display_events


def test_format_timestamp_valid():
    ts = 1721126400  # Example valid timestamp
    formatted = format_timestamp(ts)
    assert "2024-" in formatted or "2025-" in formatted


def test_format_timestamp_none():
    assert format_timestamp(None) == "N/A"


@patch("ui.services.event_utils.logger")
def test_format_timestamp_invalid(mock_logger):
    assert format_timestamp("bad") == "Invalid Timestamp"
    mock_logger.error.assert_called_once()


@patch("ui.services.event_utils.logger")
def test_display_events_normal(mock_logger):
    events = [
        {
            "label": "vehicle",
            "start_time": 1721126400,
            "end_time": 1721126460,
            "data": {"top_score": 0.92, "description": "Vehicle detected"},
            "thumbnail": "fakebase64string",
        }
    ]
    rows = display_events(events)
    assert len(rows) == 1
    assert rows[0][0] == "vehicle"
    assert "<img" in rows[0][-1]


@patch("ui.services.event_utils.logger")
def test_display_events_empty(mock_logger):
    assert display_events([]) == []
    mock_logger.info.assert_called_once_with("Displaying 0 events in table")


@patch("ui.services.event_utils.logger")
def test_display_events_malformed(mock_logger):
    events = [{"bad_key": "value"}]
    rows = display_events(events)
    assert rows == [['N/A', 'N/A', 'N/A', 'NA', 'N/A', 'No Image']]
