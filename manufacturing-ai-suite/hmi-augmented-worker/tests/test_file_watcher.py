import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
from file_watcher.file_watcher import FileChangeHandler

@pytest.fixture
def handler():
    return FileChangeHandler(existing_files=set())

@patch("builtins.open", new_callable=mock_open, read_data="file content")
@patch("requests.post")
def test_send_file_to_api_success(mock_post, mock_file, handler):
    mock_post.return_value.status_code = 200
    handler.send_file_to_api("test.txt")
    mock_post.assert_called_once()

@patch("requests.delete")
def test_delete_file_to_api_success(mock_delete, handler):
    mock_delete.return_value.status_code = 204
    handler.delete_file_to_api("test.txt")
    mock_delete.assert_called_once()

def test_should_ignore(handler):
    assert handler.should_ignore("file.swp")
    assert handler.should_ignore("file~")
    assert handler.should_ignore("4913")
    assert not handler.should_ignore("file.txt")

@patch("os.path.getsize", return_value=10)
@patch.object(FileChangeHandler, "send_file_to_api")
def test_on_modified_event(mock_send, mock_getsize, handler):
    event = MagicMock()
    event.is_directory = False
    event.src_path = "file.txt"
    event.event_type = "modified"
    handler.on_any_event(event)
    mock_send.assert_called_once_with("file.txt")

@patch.object(FileChangeHandler, "delete_file_to_api")
def test_on_deleted_event(mock_delete, handler):
    event = MagicMock()
    event.is_directory = False
    event.src_path = "file.txt"
    event.event_type = "deleted"
    handler.existing_files.add("file.txt")
    handler.on_any_event(event)
    mock_delete.assert_called_once_with("file.txt")
    assert "file.txt" not in handler.existing_files

