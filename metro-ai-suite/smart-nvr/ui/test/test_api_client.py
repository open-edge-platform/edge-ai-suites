# test/test_api_client.py

import pytest
from unittest.mock import patch, MagicMock
from ui.services.api_client import (
    fetch_cameras,
    fetch_events,
    add_rule,
    fetch_rules,
    fetch_rule_responses,
    delete_rule_by_id,
    fetch_search_responses,
    fetch_summary_status,
)

API_RULE_ID = "cam1-person-summarize-abcdef12"
SUMMARY_ID = "summary-id-001"

# === fetch_cameras ===
@patch("ui.services.api_client.requests.get")
def test_fetch_cameras_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"cameras": ["cam1", "cam2"]})
    assert fetch_cameras() == ["cam1", "cam2"]

@patch("ui.services.api_client.requests.get", side_effect=Exception("Connection failed"))
@patch("ui.services.api_client.logger")
def test_fetch_cameras_failure(mock_logger, mock_get):
    assert fetch_cameras() == []
    mock_logger.error.assert_called_once()


# === fetch_events ===
@patch("ui.services.api_client.requests.get")
def test_fetch_events_success(mock_get):
    data = [{"start_time": 1}, {"start_time": 5}, {"start_time": 2}]
    mock_get.return_value = MagicMock(status_code=200, json=lambda: data)
    result = fetch_events("cam1")
    assert result == sorted(data, key=lambda x: x["start_time"], reverse=True)

@patch("ui.services.api_client.requests.get", side_effect=Exception("Timeout"))
@patch("ui.services.api_client.logger")
def test_fetch_events_failure(mock_logger, mock_get):
    assert fetch_events("cam1") == []
    mock_logger.error.assert_called_once()


# === add_rule ===
@patch("ui.services.api_client.requests.post")
@patch("ui.services.api_client.requests.get")
def test_add_rule_success(mock_get, mock_post):
    mock_get.return_value = MagicMock(status_code=404)
    mock_post.return_value = MagicMock(status_code=200)
    response = add_rule("cam1", "person", "summarize")
    assert response["status"] == "success"
    assert "rule_id" in response

@patch("ui.services.api_client.requests.get")
def test_add_rule_exists(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    result = add_rule("cam1", "person", "summarize")
    assert result["status"] == "exists"
    assert "rule_id" in result

@patch("ui.services.api_client.requests.get", side_effect=Exception("Error checking rule"))
def test_add_rule_check_error(mock_get):
    result = add_rule("cam1", "person", "summarize")
    assert result["status"] == "error"
    assert "Error checking rule" in result["message"]

@patch("ui.services.api_client.requests.get", return_value=MagicMock(status_code=404))
@patch("ui.services.api_client.requests.post", side_effect=Exception("Post failed"))
def test_add_rule_post_error(mock_post, mock_get):
    result = add_rule("cam1", "person", "summarize")
    assert result["status"] == "error"
    assert "Post failed" in result["message"]


# === fetch_rules ===
@patch("ui.services.api_client.requests.get")
def test_fetch_rules_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: [{"id": "rule1"}])
    assert fetch_rules() == [{"id": "rule1"}]

@patch("ui.services.api_client.requests.get", side_effect=Exception("Fetch failed"))
@patch("ui.services.api_client.logger")
def test_fetch_rules_failure(mock_logger, mock_get):
    assert fetch_rules() == []
    mock_logger.error.assert_called_once()


# === fetch_rule_responses ===
@patch("ui.services.api_client.requests.get")
def test_fetch_rule_responses_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"r1": "response1"})
    assert fetch_rule_responses() == {"r1": "response1"}

@patch("ui.services.api_client.requests.get", side_effect=Exception("API Down"))
@patch("ui.services.api_client.logger")
def test_fetch_rule_responses_failure(mock_logger, mock_get):
    result = fetch_rule_responses()
    assert "error" in result
    mock_logger.error.assert_called_once()


# === delete_rule_by_id ===
@patch("ui.services.api_client.requests.delete")
def test_delete_rule_by_id_success(mock_delete):
    mock_delete.return_value = MagicMock(status_code=200)
    result = delete_rule_by_id(API_RULE_ID)
    assert result.startswith("✅")

@patch("ui.services.api_client.requests.delete")
def test_delete_rule_by_id_failure(mock_delete):
    mock_delete.return_value = MagicMock(status_code=400, text="Bad Request")
    result = delete_rule_by_id(API_RULE_ID)
    assert result.startswith("❌")

@patch("ui.services.api_client.requests.delete", side_effect=Exception("Internal Error"))
@patch("ui.services.api_client.logger")
def test_delete_rule_by_id_error(mock_logger, mock_delete):
    result = delete_rule_by_id(API_RULE_ID)
    assert "Error" in result
    mock_logger.error.assert_called_once()


# === fetch_search_responses ===
@patch("ui.services.api_client.requests.get")
def test_fetch_search_responses_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"search": "ok"})
    assert fetch_search_responses() == {"search": "ok"}

@patch("ui.services.api_client.requests.get", side_effect=Exception("Failure"))
@patch("ui.services.api_client.logger")
def test_fetch_search_responses_failure(mock_logger, mock_get):
    assert "error" in fetch_search_responses()
    mock_logger.error.assert_called_once()


# === fetch_summary_status ===
@patch("ui.services.api_client.requests.get")
def test_fetch_summary_status_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: "complete")
    assert fetch_summary_status(SUMMARY_ID) == "complete"

@patch("ui.services.api_client.requests.get", side_effect=Exception("Summary not found"))
@patch("ui.services.api_client.logger")
def test_fetch_summary_status_failure(mock_logger, mock_get):
    result = fetch_summary_status(SUMMARY_ID)
    assert "Summary not found" in result
    mock_logger.error.assert_called_once()
