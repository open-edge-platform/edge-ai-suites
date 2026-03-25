import pytest
import io
API_V1_PREFIX_MEDIA = "/api/v1/media"

def test_upload_video_endpoint(client, mock_task_service):
    file_data = {"file": ("test.mp4", io.BytesIO(b"fake-data"), "video/mp4")}
    response = client.post(f"{API_V1_PREFIX_MEDIA}/upload", files=file_data)
    assert response.status_code == 200

    res_json = response.json()
    assert res_json["code"] == 20000

    assert res_json["data"]["task_id"] == "c68211de-2187-4f52-b47d-f3a51a52b9ca"
    assert res_json["data"]["status"] == "QUEUED"

    assert "message" in res_json
    assert "timestamp" in res_json
    assert res_json["message"] == "File received, processing started."

def test_upload_ingest_endpoint(client, mock_storage, mock_task_service, mock_search_service):
    file_name = "car-detection-2min.mp4"
    file_data = {"file": (file_name, io.BytesIO(b"fake-mp4-content"), "video/mp4")}

    response = client.post(f"{API_V1_PREFIX_MEDIA}/upload-ingest", files=file_data)

    assert response.status_code == 200
    res_json = response.json()

    assert res_json["code"] == 20000
    assert res_json["message"] == "Upload and Ingest started"
    assert isinstance(res_json["timestamp"], int)

    data = res_json["data"]
    assert data["task_id"] == "c68211de-2187-4f52-b47d-f3a51a52b9ca"
    assert data["status"] == "QUEUED"
    assert "runs/" in data["file_key"]
    assert data["file_key"].endswith(file_name)

    mock_task_service.handle_file_upload.assert_called_once()
    assert response.status_code == 200

def test_file_search_endpoint(client, mock_search_service):
    payload = {"query": "how to use this", "max_num_results": 1}
    response = client.post(f"{API_V1_PREFIX_MEDIA}/search", json=payload)

    assert response.status_code == 200
    res_json = response.json()

    assert res_json["code"] == 20000
    assert res_json["message"] == "Resource found"
    assert isinstance(res_json["timestamp"], int)

    data = res_json["data"]
    assert data["resource_id"] == "res-999"
    assert data["name"] == "tutorial_01.mp4"
    assert data["type"] == "video"
    assert "https://" in data["url"]

    mock_search_service.semantic_search.assert_called_once_with("how to use this", 1)
