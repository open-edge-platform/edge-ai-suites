import pytest
from core.models import AITask

API_V1_PREFIX = "/api/v1/media"

## --- Test case 1: Asynchronous Mode (sync=False) ---
def test_submit_summary_async(client, mock_db_session, mock_redis):
    """
    Test asynchronous logic:
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
    
    # Verify database state
    task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
    assert task.status == "QUEUED"
    
    # Verify Redis call (via injected mock_redis fixture)
    mock_redis.xadd.assert_called_once()
    print("\n✅ Async submit test passed")


## --- Test case 2: Synchronous Mode (sync=True) ---
@pytest.mark.asyncio
async def test_submit_summary_sync(client, mock_db_session, mock_ai_processor):
    """
    Test synchronous logic:
    1. Status should be COMPLETED
    2. Response should contain AI processing results
    """
    # Note: mock_ai_processor uses default return_value from conftest.
    # To override for a specific test, use:
    # mock_ai_processor.return_value = {"summary": "Specific Test Summary"}

    payload = {
        "video_url": "http://example.com/test.mp4",
        "sync": True
    }
    
    response = client.post(f"{API_V1_PREFIX}/video-summary", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert "result" in data
    # Verify content matches Mock settings in conftest
    assert data["result"]["summary"] == "Mocked AI Result"
    
    # Verify database state update
    task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
    assert task.status == "COMPLETED"
    print("\n✅ Sync processing test passed")


## --- Test case 3: Query Task Status (GET) ---
def test_get_task_status(client, mock_db_session):
    """Test the query endpoint"""
    # Create mock data in the test database
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
    # Ensure ID matches after type conversion
    assert int(response.json()["id"]) == 999
    print("\n✅ Get task status test passed")


## --- Test case 4: Exception Flow ---
def test_get_nonexistent_task(client, mock_db_session):
    """Test querying a non-existent task"""
    response = client.get(f"{API_V1_PREFIX}/999999")
    assert response.status_code == 404
    print("\n✅ 404 error flow passed")