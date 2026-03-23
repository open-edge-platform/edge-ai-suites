import pytest
from core.models import AITask

# 基础路径前缀
API_V1_PREFIX = "/api/v1/tasks"

## --- Test case 1: 异步模式 (sync=False) ---
def test_submit_summary_async(client, mock_db_session, mock_redis):
    """
    测试异步逻辑：
    1. 状态应为 QUEUED
    2. 必须触发 Redis xadd
    """
    payload = {
        "video_url": "http://example.com/test.mp4",
        "sync": False,
        "callback_url": "http://webhook.site/123"
    }
    
    # 使用重构后的 URL
    response = client.post(f"{API_V1_PREFIX}/video-summary", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["mode"] == "asynchronous"
    
    # 验证数据库状态
    task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
    assert task.status == "QUEUED"
    
    # 验证 Redis 是否被调用 (通过参数注入的 mock_redis)
    mock_redis.xadd.assert_called_once()
    print("\n✅ Async submit test passed")


## --- Test case 2: 同步模式 (sync=True) ---
@pytest.mark.asyncio
async def test_submit_summary_sync(client, mock_db_session, mock_ai_processor):
    """
    测试同步逻辑：
    1. 状态应为 COMPLETED
    2. 响应应包含 AI 处理结果
    """
    # 这里的 mock_ai_processor 已经在 conftest 中设置了默认 return_value
    # 如果想在这个特定测试中改返回值，可以这样：
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
    # 验证返回内容是否匹配 conftest 中的 Mock 设置
    assert data["result"]["summary"] == "Mocked AI Result"
    
    # 验证数据库状态更新
    task = mock_db_session.query(AITask).filter(AITask.id == data["task_id"]).first()
    assert task.status == "COMPLETED"
    print("\n✅ Sync processing test passed")


## --- Test case 3: 获取任务状态 (GET) ---
def test_get_task_status(client, mock_db_session):
    """测试查询接口"""
    # 先在 Mock DB 中造一条数据
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


## --- Test case 4: 异常流 ---
def test_get_nonexistent_task(client, mock_db_session):
    """测试查询不存在的任务"""
    response = client.get(f"{API_V1_PREFIX}/999999")
    assert response.status_code == 404
    print("\n✅ 404 error flow passed")