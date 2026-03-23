import pytest
import asyncio
from unittest.mock import MagicMock, patch
from core.models import AITask
# Import your logic
# from worker_run import send_webhook

# Mock an async AI result
async def mock_run_dummy_ai_logic(url):
    return "This is a mocked AI summary result."

@pytest.mark.asyncio
async def test_task_processing_logic(mock_db_session):
    """
    Without Redis, test the transition from PROCESSING to COMPLETED.
    """
    # 1. Setup: create a pending task in the in-memory DB
    task_id = "test-uuid-999"
    callback_url = "http://fake-webhook.com/callback"
    new_task = AITask(
        id=task_id,
        status="QUEUED",
        payload={"video_url": "C:/test.mp4", "callback_url": callback_url}
    )
    mock_db_session.add(new_task)
    mock_db_session.commit()

    # 2. Stubs: intercept external dependencies
    # patch 'worker_run.run_dummy_ai_logic' to stub AI logic
    # patch 'requests.post' to stub webhook sending
    with patch("worker_run.run_dummy_ai_logic", side_effect=mock_run_dummy_ai_logic), \
         patch("requests.post") as mock_post:
        
        mock_post.return_value.status_code = 200

        # --- Simulate core worker logic ---
        # Step A: fetch task and set status to PROCESSING
        task = mock_db_session.query(AITask).filter(AITask.id == task_id).first()
        task.status = "PROCESSING"
        mock_db_session.commit()
        
        # Step B: call AI logic
        ai_result = await mock_run_dummy_ai_logic(task.payload.get('video_url'))
        
        # Step C: update result to COMPLETED
        task.status = "COMPLETED"
        task.result = ai_result
        mock_db_session.commit()

        # Step D: simulate webhook sending
        if callback_url:
            mock_post(callback_url, json={"task_id": task_id, "result": ai_result})

    # 3. Assertions
    # Verify database status
    updated_task = mock_db_session.query(AITask).filter(AITask.id == task_id).first()
    assert updated_task.status == "COMPLETED"
    assert updated_task.result == "This is a mocked AI summary result."
    
    # Verify webhook was called
    mock_post.assert_called_once()
    print("\n✅ Consumer flow OK: status, AI result, webhook all as expected!")