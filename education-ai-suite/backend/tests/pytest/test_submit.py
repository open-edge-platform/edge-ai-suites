import pytest
from core.models import AITask

API_V1_PREFIX = "/api/v1/tasks"

def test_submit_summary_async(client, mock_db_session, mock_redis):
    """
    Test sync=False logic:
    1. Status should be QUEUED
    2. Redis xadd must be triggered
    """
    payload = {
        "video_url": "http://example.com/test.mp4",
        "sync": False,
        "callback_url": "http://webhook.site/123"
    }

    response = client.post(f"{API_V1_PREFIX}/video-summary", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["mode"] == "asynchronous"

    task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
    assert task.status == "QUEUED"

    mock_redis.xadd.assert_called_once()
    print("\n✅ Async submit test passed")


@pytest.mark.asyncio
async def test_submit_summary_sync(client, mock_db_session, mock_ai_processor):
    """
    Test sync=True logic:
    1. Status should become COMPLETED
    2. Response should contain result
    """
    payload = {
        "video_url": "http://example.com/test.mp4",
        "sync": True
    }
    
    response = client.post(f"{API_V1_PREFIX}/video-summary", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert "result" in data
    assert data["result"]["summary"] == "Mocked AI Result"

    task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
    assert task.status == "COMPLETED"
    print("\n✅ Sync processing test passed")

def test_get_task_status(client, mock_db_session):
    new_task = AITask(
        id=999,
        task_type="video_summary",
        status="COMPLETED",
        payload={"video_url": "test.mp4"},
        result={"summary": "Historical result"},
        user_id="admin"
    )
    mock_db_session.add(new_task)
    mock_db_session.commit()

    response = client.get(f"{API_V1_PREFIX}/999")
    
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    # assert response.json()["id"] == 999
    assert int(response.json()["id"]) == 999
    print("\n✅ Get task status test passed")

def test_get_nonexistent_task(client, mock_db_session):
    response = client.get(f"{API_V1_PREFIX}/999999")
    assert response.status_code == 404
    print("\n✅ 404 error flow passed")