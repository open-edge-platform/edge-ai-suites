import pytest
from unittest.mock import patch, AsyncMock
from core.models import AITask

# Mock AI handler (corresponds to run_dummy_ai_logic in api/route.py)
# If the function is not defined yet, we can patch it in tests
async def mock_ai_work(url):
    return {"summary": "This is a mocked AI video summary", "duration": 120}

## --- Test case 1: async callback mode ---
def test_submit_summary_async(client, mock_db_session):
    """
    Test sync=False logic:
    1. Status should be QUEUED
    2. Redis xadd must be triggered
    """
    with patch("api.route.redis_client") as mock_redis:
        payload = {
            "video_url": "http://example.com/test.mp4",
            "sync": False,
            "callback_url": "http://webhook.site/123"
        }
        
        response = client.post("/api/tasks/video-summary", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["mode"] == "asynchronous"
        
        # Verify DB status
        task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
        assert task.status == "QUEUED"
        
        # Verify Redis was called
        mock_redis.xadd.assert_called_once()
        print("\n✅ Async submit test passed")

## --- Test case 2: synchronous mode ---
@pytest.mark.asyncio  # Recommended when mocking async functions
async def test_submit_summary_sync(client, mock_db_session):
    """
    Test sync=True logic:
    1. Status should become COMPLETED
    2. Response should contain result
    """
    # Assume api/route.py calls run_dummy_ai_logic
    # Intercept the expensive call and return a mocked result
    with patch("api.route.run_dummy_ai_logic", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"summary": "Synchronous processing OK"}
        
        payload = {
            "video_url": "http://example.com/test.mp4",
            "sync": True
        }
        
        response = client.post("/api/tasks/video-summary", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert "result" in data
        assert data["result"]["summary"] == "Synchronous processing OK"
        
        # Verify DB status updated to COMPLETED
        task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
        assert task.status == "COMPLETED"
        print("\n✅ Sync processing test passed")

## --- Test case 3: error flow (optional) ---
def test_submit_summary_invalid_payload(client, mock_db_session):
    """Test missing required fields like video_url (if validation exists)."""
    # If validation is missing, it may still write to DB; demo only
    response = client.post("/api/tasks/video-summary", json={})
    # Depending on your logic, it may be 200 or 422
    assert response.status_code in [200, 422]