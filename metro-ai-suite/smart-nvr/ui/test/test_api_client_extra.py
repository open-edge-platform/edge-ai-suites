"""Extra tests for api_client covering cameras with mapping dict and plain list cases."""
from unittest.mock import patch, MagicMock
from ui.services import api_client

@patch("ui.services.api_client.requests.get")
def test_fetch_cameras_with_labels_mapping(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"cameras": {"garage": ["car"], "livingroom": []}})
    names, mapping = api_client.fetch_cameras_with_labels()
    assert set(names) == {"garage", "livingroom"}
    assert mapping["garage"] == ["car"]

@patch("ui.services.api_client.requests.get")
def test_fetch_cameras_with_labels_plain_list(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"cameras": ["cam1", "cam2"]})
    names, mapping = api_client.fetch_cameras_with_labels()
    assert names == ["cam1", "cam2"]
    assert mapping["cam1"] == []

@patch("ui.services.api_client.requests.get")
def test_fetch_cameras_with_labels_fallback_mapping(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"garage": ["person", "car"]})
    names, mapping = api_client.fetch_cameras_with_labels()
    assert names == ["garage"]
    assert mapping["garage"] == ["person", "car"]
