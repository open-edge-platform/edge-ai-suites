import pytest
from unittest.mock import patch, AsyncMock
from core.models import AITask

@pytest.mark.asyncio
async def test_worker_handle_task_success(mock_db_session):
    task_id = "test-123"
    new_task = AITask(id=task_id, status="QUEUED", payload={"video_url": "v.mp4"})
    mock_db_session.add(new_task)
    mock_db_session.commit()

    with patch("processor.run_dummy_ai_logic", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"summary": "car detected"}

        from worker_run import handle_task
        await handle_task(mock_db_session, task_id, "stream:video_processing")

    mock_db_session.expire_all()
    updated_task = mock_db_session.query(AITask).filter_by(id=task_id).first()
    assert updated_task.status == "COMPLETED"